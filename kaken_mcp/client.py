"""Asynchronous client for the official KAKEN OpenSearch APIs."""

import asyncio
import json
import re
import time
from collections.abc import Iterable, Mapping
from typing import Any, cast
from xml.etree import ElementTree

import httpx

from kaken_mcp.config import Settings


class KakenError(Exception):
    """Exception raised when a KAKEN API operation fails."""


class KakenClient:
    """Client for the KAKEN project and researcher OpenSearch APIs."""

    _VALID_PAGE_SIZES = (20, 50, 100, 200, 500)

    def __init__(self, settings: Settings) -> None:
        """Initialize the client without making a network request."""
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._rate_limit_lock = asyncio.Lock()
        self._next_request_at = 0.0

    def _http_client(self) -> httpx.AsyncClient:
        """Return the shared HTTP client, recreating it after close."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.settings.request_timeout,
                headers={
                    "User-Agent": self.settings.user_agent,
                    "Accept": "application/xml, application/json",
                    "Accept-Language": "ja",
                },
                follow_redirects=True,
                trust_env=False,
            )
        return self._client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "KakenClient":
        """Enter an asynchronous context."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the client when leaving an asynchronous context."""
        await self.close()

    async def search_projects(
        self,
        keyword: str | None = None,
        title: str | None = None,
        researcher_name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        fiscal_year_from: int | None = None,
        fiscal_year_to: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search research projects and return the legacy normalized shape."""
        params: dict[str, str] = {}
        self._set_if_value(params, "kw", keyword)
        self._set_if_value(params, "qa", title)
        self._set_if_value(params, "qg", researcher_name)
        self._set_if_value(params, "qm", researcher_number)
        self._set_if_value(params, "qe", institution)
        self._set_if_value(params, "qd", research_field)
        if fiscal_year_from is not None:
            params["s1"] = str(fiscal_year_from)
        if fiscal_year_to is not None:
            params["s2"] = str(fiscal_year_to)
        if not params:
            raise KakenError("At least one project search condition is required")
        if (
            fiscal_year_from is not None
            and fiscal_year_to is not None
            and fiscal_year_from > fiscal_year_to
        ):
            raise KakenError("fiscal_year_from must not exceed fiscal_year_to")
        return await self._search_projects(params, limit, offset)

    async def get_project_detail(self, project_id: str) -> dict[str, Any]:
        """Get one project via the API's project-number search parameter."""
        numeric_id = project_id.removeprefix("KAKENHI-PROJECT-")
        if not re.fullmatch(r"[0-9A-Za-z]+", numeric_id):
            raise KakenError(f"Invalid project ID: {project_id!r}")

        result = await self._search_projects({"qb": numeric_id}, 20, 0)
        projects = cast(list[dict[str, Any]], result["projects"])
        expected_id = f"KAKENHI-PROJECT-{numeric_id}"
        project = next((item for item in projects if item.get("id") == expected_id), None)
        if project is None:
            raise KakenError(f"Project not found: {project_id!r}")
        return project

    async def search_researchers(
        self,
        name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search researchers and return the legacy normalized shape."""
        if not any((name, researcher_number, institution, research_field)):
            raise KakenError("At least one researcher search condition is required")
        requested_limit = self._requested_limit(limit)
        params = self._base_params("json", requested_limit, offset, max_start=1000)
        self._set_if_value(params, "qg", name)
        self._set_if_value(params, "qm", researcher_number)
        self._set_if_value(params, "qh", institution)
        self._set_if_value(params, "qd", research_field)
        body = await self._request(self.settings.researcher_api_url, params, "json")
        result = self._parse_researcher_results(body)
        result["researchers"] = result["researchers"][:requested_limit]
        return result

    async def get_researcher_projects(
        self,
        researcher_number: str,
        role: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get projects associated with a researcher, optionally by role."""
        params = {"qm": researcher_number}
        if role:
            normalized_role = role.lower()
            if normalized_role in {"principal", "代表者", "研究代表者"}:
                params["c2"] = "principal_investigator"
            elif normalized_role in {"co-investigator", "分担者", "研究分担者"}:
                params["c2"] = "co_investigator_buntan"
        return await self._search_projects(params, limit, offset)

    async def _search_projects(
        self, query: dict[str, str], limit: int | None, offset: int
    ) -> dict[str, Any]:
        requested_limit = self._requested_limit(limit)
        params = self._base_params("xml", requested_limit, offset, max_start=200000)
        params.update(query)
        body = await self._request(self.settings.project_api_url, params, "xml")
        result = self._parse_search_results(body)
        result["projects"] = result["projects"][:requested_limit]
        return result

    def _base_params(
        self, format_name: str, limit: int, offset: int, *, max_start: int
    ) -> dict[str, str]:
        if offset < 0:
            raise KakenError("offset must be zero or greater")
        if offset + 1 > max_start:
            raise KakenError(f"offset exceeds the API maximum start position of {max_start}")
        return {
            "appid": self._app_id(),
            "format": format_name,
            "lang": "ja",
            "rw": str(self._page_size(limit)),
            "st": str(offset + 1),
        }

    def _app_id(self) -> str:
        app_id = self.settings.app_id
        if app_id is None or not app_id.get_secret_value():
            raise KakenError("KAKEN_APP_ID is required to call the KAKEN OpenSearch API")
        return app_id.get_secret_value()

    def _requested_limit(self, limit: int | None) -> int:
        requested = self.settings.default_limit if limit is None else limit
        if requested <= 0:
            raise KakenError("limit must be greater than zero")
        maximum = min(self.settings.max_limit, self._VALID_PAGE_SIZES[-1])
        if maximum <= 0:
            raise KakenError("KAKEN_MAX_LIMIT must be greater than zero")
        return min(requested, maximum)

    @classmethod
    def _page_size(cls, limit: int) -> int:
        return next(size for size in cls._VALID_PAGE_SIZES if size >= limit)

    @staticmethod
    def _set_if_value(params: dict[str, str], key: str, value: str | None) -> None:
        if value:
            params[key] = value

    async def _throttle(self) -> None:
        """Reserve one rate-limited request slot."""
        async with self._rate_limit_lock:
            now = time.monotonic()
            start_at = max(now, self._next_request_at)
            self._next_request_at = start_at + self.settings.request_delay
        delay = start_at - now
        if delay > 0:
            await asyncio.sleep(delay)

    async def _request(self, url: str, params: dict[str, str], expected_format: str) -> str:
        """Request one API response with throttling, retry, and media validation."""
        for attempt in range(self.settings.max_retries):
            await self._throttle()
            try:
                response = await self._http_client().get(url, params=params)
                response.raise_for_status()
                self._raise_api_error(response.text)
                self._validate_content_type(response, expected_format)
                return response.text
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                is_rate_limited = status == 429 or (
                    status == 403 and self._is_rate_limit_response(error.response.text)
                )
                if 400 <= status < 500 and not is_rate_limited:
                    raise KakenError(f"KAKEN API request failed with status {status}") from None
            except httpx.RequestError:
                pass

            if attempt < self.settings.max_retries - 1:
                await asyncio.sleep(self.settings.retry_delay * (2**attempt))

        raise KakenError(f"KAKEN API request failed after {self.settings.max_retries} attempts")

    @staticmethod
    def _validate_content_type(response: httpx.Response, expected_format: str) -> None:
        content_type = response.headers.get("content-type", "").lower()
        valid = "xml" in content_type if expected_format == "xml" else "json" in content_type
        if not valid:
            raise KakenError(f"KAKEN API returned an unexpected content type for {expected_format}")

    @classmethod
    def _raise_api_error(cls, body: str) -> None:
        """Recognize the API's XML error envelope without echoing its detail."""
        if not body.lstrip().startswith("<"):
            return
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError:
            return
        if cls._local_name(root.tag) != "error":
            return
        code = cls._child_text(root, "code") or "unknown"
        reason = cls._child_text(root, "reason") or "unknown error"
        raise KakenError(f"KAKEN API error {code}: {reason}")

    @classmethod
    def _is_rate_limit_response(cls, body: str) -> bool:
        """Identify NII's 403 rate-limit envelope without exposing its body."""
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError:
            return False
        return (
            cls._local_name(root.tag) == "error"
            and "rate" in cls._child_text(root, "detail").lower()
        )

    def _parse_search_results(self, xml_text: str) -> dict[str, Any]:
        """Normalize a project XML response."""
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            raise KakenError("KAKEN API returned invalid XML") from None

        projects = [self._parse_project(element) for element in self._children(root, "grantAward")]
        total_count = self._as_int(self._descendant_text(root, "totalResults")) or 0
        return {"total_count": total_count, "projects": projects}

    def _parse_project(self, grant: ElementTree.Element) -> dict[str, Any]:
        summary = self._localized_child(grant, "summary")
        raw_project_id = (
            grant.attrib.get("awardNumber")
            or self._award_number(summary)
            or grant.attrib.get("id", "")
        )
        project_id = raw_project_id.removeprefix("KAKENHI-PROJECT-")
        api_url = self._localized_url(grant)
        project: dict[str, Any] = {
            "id": f"KAKENHI-PROJECT-{project_id}",
            "url": api_url or self._project_url(project_id),
        }

        self._put(project, "title", self._child_text(summary, "title"))
        category_fc = self._child_text(summary, "categoryFc")
        categories = self._child_texts(summary, "category")
        if category_fc:
            project["research_category"] = category_fc
        elif categories:
            project["research_category"] = categories[-1]
        institutions = self._ordered_children(summary, "institution")
        if institutions:
            self._put(project, "institution", "".join(institutions[0].itertext()).strip())

        members = self._ordered_children(summary, "member")
        principal = next(
            (
                member
                for member in members
                if member.attrib.get("role") in {"principal_investigator", "area_organizer"}
            ),
            None,
        )
        if principal is not None:
            self._put(
                project,
                "principal_investigator",
                self._project_member_name(principal),
            )
            if "institution" not in project:
                self._put(
                    project,
                    "institution",
                    self._descendant_text(principal, "institution"),
                )

        researchers = [self._parse_project_member(member) for member in members]
        researchers = [researcher for researcher in researchers if researcher]
        if researchers:
            project["researchers"] = researchers

        period = self._child(summary, "periodOfAward")
        if period is not None:
            start = self._period_year(period, "Start")
            end = self._period_year(period, "End")
            if start is not None:
                project["fiscal_year_start"] = start
            if end is not None:
                project["fiscal_year_end"] = end
            if start is not None:
                project["fiscal_years"] = str(start) if end is None else f"{start} - {end}"

        status = self._child(summary, "projectStatus")
        if status is not None and status.attrib.get("statusCode"):
            project["status"] = status.attrib["statusCode"]

        keywords_parent = self._child(summary, "keywordList")
        if keywords_parent is not None:
            keywords = self._ordered_texts(keywords_parent, "keyword")
            if keywords:
                project["keywords"] = keywords

        paragraphs = self._children(summary, "paragraphList")
        abstract = next(
            (item for item in paragraphs if item.attrib.get("type") == "abstract"),
            None,
        )
        if abstract is None:
            abstract = next(
                (
                    item
                    for item in paragraphs
                    if item.attrib.get("type") == "outline_of_research_initial"
                ),
                None,
            )
        if abstract is not None:
            summary_text = "\n".join(self._ordered_texts(abstract, "paragraph"))[:1000]
            self._put(project, "summary", summary_text)

        review_sections = self._ordered_texts(summary, "review_section")
        fields = self._ordered_texts(summary, "field")
        if review_sections:
            project["review_section"] = review_sections[0]
        if fields:
            project["research_field"] = fields[0]

        amounts = self._ordered_children(summary, "overallAwardAmount")
        amount = next((item for item in amounts if item.attrib.get("planned") != "true"), None)
        if amount is None and amounts:
            amount = amounts[0]
        if amount is not None:
            total = self._cost_value(amount, "convertedJpyTotalCost")
            if total is None:
                total = self._cost_value(amount, "totalCost")
            if total is not None:
                project["total_budget"] = total
        return project

    def _parse_project_member(self, member: ElementTree.Element) -> dict[str, Any]:
        researcher: dict[str, Any] = {}
        self._put(researcher, "name", self._project_member_name(member))
        self._put(researcher, "role", member.attrib.get("role", ""))
        self._put(
            researcher,
            "researcher_number",
            member.attrib.get("researcherNumber", "") or member.attrib.get("eradCode", ""),
        )
        self._put(researcher, "institution", self._descendant_text(member, "institution"))
        return researcher

    def _project_member_name(self, member: ElementTree.Element) -> str:
        names = self._ordered_children(member, "personalName")
        return self._descendant_text(names[0], "fullName") if names else ""

    def _cost_value(self, amount: ElementTree.Element, name: str) -> int | None:
        element = self._child(amount, name)
        if element is None:
            return None
        normalized = self._descendant_text(element, "normalizedValue")
        return self._as_int(normalized or "".join(element.itertext()).strip())

    def _period_year(self, period: ElementTree.Element, boundary: str) -> int | None:
        search_year = self._as_int(period.attrib.get(f"search{boundary}FiscalYear"))
        fiscal_year = self._as_int(self._child_text(period, f"{boundary.lower()}FiscalYear"))
        date = self._child_text(period, f"{boundary.lower()}Date")
        date_match = re.fullmatch(r"(\d{4})-(\d{2})-\d{2}", date)
        date_year = None
        if date_match:
            year, month = (int(part) for part in date_match.groups())
            date_year = year if month >= 4 else year - 1
        return search_year or fiscal_year or date_year

    def _parse_researcher_results(self, json_text: str) -> dict[str, Any]:
        """Normalize a researcher JSON response."""
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            raise KakenError("KAKEN API returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise KakenError("KAKEN API returned an invalid researcher response")

        raw_researchers = payload.get("researchers", [])
        if not isinstance(raw_researchers, list):
            raise KakenError("KAKEN API returned an invalid researcher response")
        researchers = [
            self._parse_researcher(item) for item in raw_researchers if isinstance(item, dict)
        ]
        total = self._as_int(payload.get("totalResults")) or 0
        return {"total_count": total, "researchers": researchers}

    def _parse_researcher(self, researcher: Mapping[str, Any]) -> dict[str, Any]:
        number = ""
        record_source = researcher.get("recordSource")
        if isinstance(record_source, Mapping):
            number = self._first_string(record_source.get("id:person:kakenhi"))
        if not number:
            number = self._first_string(researcher.get("id:person:erad"))

        accn = researcher.get("accn")
        nrid = accn if isinstance(accn, str) and re.fullmatch(r"\d{13}", accn) else f"1000{number}"

        result: dict[str, Any] = {
            "researcher_number": number,
            "name": self._human_text(researcher.get("name")),
            "url": f"{self.settings.researcher_base_url}/ja/nrid/{nrid}/",
        }
        affiliations = researcher.get("affiliations:current")
        if isinstance(affiliations, list) and affiliations:
            affiliation = min(
                (item for item in affiliations if isinstance(item, Mapping)),
                key=self._mapping_sequence,
                default=None,
            )
            if isinstance(affiliation, Mapping):
                institution = self._human_text(affiliation.get("affiliation:institution"))
                department = self._human_text(affiliation.get("affiliation:department"))
                job_title = self._human_text(affiliation.get("affiliation:jobTitle"))
                parts = [part for part in (institution, department, job_title) if part]
                if parts:
                    result["affiliation"] = " ".join(parts)
                self._put(result, "institution", institution)
                self._put(result, "department", department)
                self._put(result, "job_title", job_title)
        return result

    def _project_url(self, project_id: str) -> str:
        return f"{self.settings.base_url}/ja/grant/KAKENHI-PROJECT-{project_id}/"

    @classmethod
    def _localized_url(cls, grant: ElementTree.Element) -> str:
        url_list = cls._child(grant, "urlList")
        if url_list is None:
            return ""
        urls = cls._children(url_list, "url")
        lang_key = "{http://www.w3.org/XML/1998/namespace}lang"
        selected = next((item for item in urls if item.attrib.get(lang_key) == "ja"), None)
        if selected is None and urls:
            selected = urls[0]
        return "" if selected is None else "".join(selected.itertext()).strip()

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _children(cls, element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
        return [child for child in element if cls._local_name(child.tag) == name]

    @classmethod
    def _ordered_children(
        cls, element: ElementTree.Element, name: str
    ) -> list[ElementTree.Element]:
        def sequence(item: ElementTree.Element) -> int:
            return cls._as_int(item.attrib.get("sequence")) or 1_000_000

        return sorted(cls._children(element, name), key=sequence)

    @classmethod
    def _ordered_texts(cls, element: ElementTree.Element, name: str) -> list[str]:
        return [
            text
            for child in cls._ordered_children(element, name)
            if (text := "".join(child.itertext()).strip())
        ]

    @classmethod
    def _child(cls, element: ElementTree.Element, name: str) -> ElementTree.Element | None:
        return next(iter(cls._children(element, name)), None)

    @classmethod
    def _localized_child(cls, element: ElementTree.Element, name: str) -> ElementTree.Element:
        candidates = cls._children(element, name)
        if not candidates:
            return ElementTree.Element(name)
        lang_key = "{http://www.w3.org/XML/1998/namespace}lang"
        return next(
            (item for item in candidates if item.attrib.get(lang_key) == "ja"),
            candidates[0],
        )

    @classmethod
    def _child_text(cls, element: ElementTree.Element, name: str) -> str:
        child = cls._child(element, name)
        return "" if child is None else "".join(child.itertext()).strip()

    @classmethod
    def _child_texts(cls, element: ElementTree.Element, name: str) -> list[str]:
        return [
            text
            for child in cls._children(element, name)
            if (text := "".join(child.itertext()).strip())
        ]

    @classmethod
    def _descendant_text(cls, element: ElementTree.Element, name: str) -> str:
        descendant = next(
            (item for item in element.iter() if cls._local_name(item.tag) == name), None
        )
        return "" if descendant is None else "".join(descendant.itertext()).strip()

    @classmethod
    def _award_number(cls, summary: ElementTree.Element) -> str:
        award = cls._child(summary, "awardNumber")
        if award is None:
            return ""
        return award.attrib.get("awardNumber") or "".join(award.itertext()).strip()

    @staticmethod
    def _as_int(value: object) -> int | None:
        try:
            return int(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _put(target: dict[str, Any], key: str, value: str) -> None:
        if value:
            target[key] = value

    @classmethod
    def _human_text(cls, value: object) -> str:
        if isinstance(value, Mapping):
            value = value.get("humanReadableValue", value.get("text", ""))
        if isinstance(value, list):
            japanese = next(
                (item for item in value if isinstance(item, Mapping) and item.get("lang") == "ja"),
                None,
            )
            fallback = japanese if japanese is not None else (value[0] if value else "")
            return cls._human_text(fallback)
        if isinstance(value, Mapping):
            text = value.get("text", "")
            return text if isinstance(text, str) else ""
        return value if isinstance(value, str) else ""

    @staticmethod
    def _first_string(value: object) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            return next((item for item in value if isinstance(item, str)), "")
        return ""

    @staticmethod
    def _mapping_sequence(value: Mapping[str, Any]) -> int:
        sequence = KakenClient._as_int(value.get("sequence"))
        return sequence if sequence is not None else 1_000_000
