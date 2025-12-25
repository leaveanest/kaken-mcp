"""KAKEN client for scraping research project and researcher data from website."""

import asyncio
import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from kaken_mcp.config import Settings


class KakenError(Exception):
    """Exception raised when KAKEN request fails."""


class KakenClient:
    """Client for scraping KAKEN website."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the KAKEN client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            },
            follow_redirects=True,
        )
        self._last_request_time: float = 0.0

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "KakenClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
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
        """Search for research projects by scraping KAKEN website.

        Args:
            keyword: Free text search keyword
            title: Research project title
            researcher_name: Name of researcher
            researcher_number: Researcher number
            institution: Research institution name
            research_field: Research field
            fiscal_year_from: Start fiscal year
            fiscal_year_to: End fiscal year
            limit: Maximum number of results
            offset: Starting position for pagination

        Returns:
            Dictionary containing search results with total_count and projects list
        """
        params: dict[str, str] = {}

        # Build search query
        if keyword:
            params["kw"] = keyword
        if title:
            params["q1"] = title
        if researcher_name:
            params["q4"] = researcher_name
        if researcher_number:
            params["q15"] = researcher_number
        if institution:
            params["q5"] = institution
        if research_field:
            params["q2"] = research_field
        if fiscal_year_from:
            params["q7"] = str(fiscal_year_from)
        if fiscal_year_to:
            params["q8"] = str(fiscal_year_to)

        # Pagination - KAKEN requires minimum 20 results per page
        requested_limit = limit or self.settings.default_limit
        # Request at least 20 to avoid empty responses from KAKEN
        actual_limit = max(20, min(requested_limit, self.settings.max_limit))
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.base_url}/ja/search/"
        html = await self._request(url, params)
        result = self._parse_search_results(html)

        # Slice results if user requested fewer than 20
        if requested_limit < len(result["projects"]):
            result["projects"] = result["projects"][:requested_limit]

        return result

    async def get_project_detail(self, project_id: str) -> dict[str, Any]:
        """Get detailed information for a specific research project.

        Args:
            project_id: Research project ID (e.g., "KAKENHI-PROJECT-19H00001" or "19H00001")

        Returns:
            Dictionary containing project details
        """
        # Extract numeric ID if full format is provided
        numeric_id = project_id
        if "KAKENHI-PROJECT-" in project_id:
            numeric_id = project_id.replace("KAKENHI-PROJECT-", "")

        url = f"{self.settings.base_url}/ja/grant/KAKENHI-PROJECT-{numeric_id}/"
        html = await self._request(url)
        return self._parse_project_detail(html, numeric_id)

    async def search_researchers(
        self,
        name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for researchers by scraping NRID website.

        Args:
            name: Researcher name
            researcher_number: Researcher number
            institution: Research institution name
            research_field: Research field
            limit: Maximum number of results
            offset: Starting position for pagination

        Returns:
            Dictionary containing search results with total_count and researchers list
        """
        params: dict[str, str] = {}

        # Build query using kw parameter
        query_parts: list[str] = []
        if name:
            query_parts.append(name)
        if institution:
            query_parts.append(institution)
        if research_field:
            query_parts.append(research_field)

        if query_parts:
            params["kw"] = " ".join(query_parts)
        if researcher_number:
            params["qn"] = researcher_number

        # Pagination - NRID requires minimum 20 results per page
        requested_limit = limit or self.settings.default_limit
        actual_limit = max(20, min(requested_limit, self.settings.max_limit))
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.researcher_base_url}/ja/search/"
        html = await self._request(url, params)
        result = self._parse_researcher_results(html)

        # Slice results if user requested fewer than 20
        if requested_limit < len(result["researchers"]):
            result["researchers"] = result["researchers"][:requested_limit]

        return result

    async def get_researcher_projects(
        self,
        researcher_number: str,
        role: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get research projects for a specific researcher.

        Args:
            researcher_number: Researcher number
            role: Role filter (e.g., "principal", "co-investigator")
            limit: Maximum number of results
            offset: Starting position for pagination

        Returns:
            Dictionary containing search results
        """
        params: dict[str, str] = {"q15": researcher_number}

        if role:
            if role.lower() in ["principal", "代表者", "研究代表者"]:
                params["q13"] = "1"
            elif role.lower() in ["co-investigator", "分担者", "研究分担者"]:
                params["q13"] = "2"

        # Pagination - KAKEN requires minimum 20 results per page
        requested_limit = limit or self.settings.default_limit
        actual_limit = max(20, min(requested_limit, self.settings.max_limit))
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.base_url}/ja/search/"
        html = await self._request(url, params)
        result = self._parse_search_results(html)

        # Slice results if user requested fewer than 20
        if requested_limit < len(result["projects"]):
            result["projects"] = result["projects"][:requested_limit]

        return result

    async def _request(
        self, url: str, params: dict[str, str] | None = None
    ) -> str:
        """Make an HTTP request with rate limiting and retry logic.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            Response HTML text

        Raises:
            KakenError: If the request fails after all retries
        """
        # Rate limiting - wait if necessary
        elapsed = time.time() - self._last_request_time
        if elapsed < self.settings.request_delay:
            await asyncio.sleep(self.settings.request_delay - elapsed)

        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            try:
                response = await self._client.get(url, params=params)
                response.raise_for_status()
                self._last_request_time = time.time()
                return response.text
            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise KakenError(
                        f"Request failed with status {e.response.status_code}"
                    ) from e
                last_error = e
            except httpx.RequestError as e:
                last_error = e

            # Exponential backoff for retries
            if attempt < self.settings.max_retries - 1:
                delay = self.settings.retry_delay * (2**attempt)
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_error:
            msg = f"Request failed after {self.settings.max_retries} retries: {last_error}"
            raise KakenError(msg) from last_error
        raise KakenError("Request failed with unknown error")

    def _parse_search_results(self, html: str) -> dict[str, Any]:
        """Parse search results HTML.

        Args:
            html: HTML response text

        Returns:
            Parsed results as dictionary
        """
        soup = BeautifulSoup(html, "lxml")
        projects: list[dict[str, Any]] = []

        # Find total count - try multiple patterns
        total_count = 0

        # Pattern 1: "検索結果: X件" format
        for text in soup.find_all(string=re.compile(r"[\d,]+件")):
            text_str = str(text)
            match = re.search(r"([\d,]+)件", text_str)
            if match:
                total_count = int(match.group(1).replace(",", ""))
                break

        # Pattern 2: Class-based selectors (fallback)
        if total_count == 0:
            count_elem = soup.select_one(".search-result-count, .result-count, strong")
            if count_elem:
                count_text = count_elem.get_text()
                numbers = re.findall(r"[\d,]+", count_text)
                if numbers:
                    total_count = int(numbers[0].replace(",", ""))

        # Parse each project entry
        # Try multiple selectors for different page structures
        entries = soup.select(".search-result-item, .result-item, article, .grant-item")

        if not entries:
            # Fallback: look for h3 with links to grant pages
            for h3 in soup.find_all("h3"):
                link = h3.find("a", href=re.compile(r"/grant/"))
                if link:
                    project = self._parse_project_from_list(h3.parent or h3)
                    if project:
                        projects.append(project)
        else:
            for entry in entries:
                project = self._parse_project_from_list(entry)
                if project:
                    projects.append(project)

        return {
            "total_count": total_count,
            "projects": projects,
        }

    def _parse_project_from_list(self, element: Tag) -> dict[str, Any] | None:
        """Parse a single project entry from search results.

        Args:
            element: BeautifulSoup element containing project info

        Returns:
            Project data as dictionary or None if parsing fails
        """
        project: dict[str, Any] = {}

        # Find title and URL
        title_link = element.find("a", href=re.compile(r"/grant/"))
        if title_link:
            project["title"] = title_link.get_text(strip=True)
            href_attr = title_link.get("href", "")
            href = str(href_attr) if href_attr else ""
            if href:
                if href.startswith("/"):
                    project["url"] = f"{self.settings.base_url}{href}"
                else:
                    project["url"] = href
                # Extract project ID from URL
                match = re.search(r"KAKENHI-PROJECT-([A-Z0-9]+)", href)
                if match:
                    project["id"] = f"KAKENHI-PROJECT-{match.group(1)}"

        if not project.get("title"):
            return None

        # Find researcher info (usually in h4 or similar)
        researcher_elem = element.find("h4")
        if researcher_elem:
            text = researcher_elem.get_text(strip=True)
            # Parse "研究者名 所属, 部局, 職位" format
            parts = text.split(",")
            if parts:
                project["principal_investigator"] = parts[0].strip()
            if len(parts) > 1:
                project["institution"] = parts[1].strip()

        # Find research period
        period_text = element.get_text()
        period_match = re.search(r"(\d{4})[年\-/]?\s*[-–～~]\s*(\d{4})?", period_text)
        if period_match:
            project["fiscal_year_start"] = int(period_match.group(1))
            if period_match.group(2):
                project["fiscal_year_end"] = int(period_match.group(2))

        # Find budget amount (require at least one digit)
        budget_match = re.search(r"[¥￥]\s*([\d,]+)", period_text)
        if budget_match and budget_match.group(1):
            amount_str = budget_match.group(1).replace(",", "")
            if amount_str.isdigit():
                project["total_budget"] = int(amount_str)

        return project

    def _parse_project_detail(self, html: str, project_id: str) -> dict[str, Any]:
        """Parse project detail page HTML.

        Args:
            html: HTML response text
            project_id: Project ID for reference

        Returns:
            Parsed project details as dictionary
        """
        soup = BeautifulSoup(html, "lxml")
        project: dict[str, Any] = {
            "id": f"KAKENHI-PROJECT-{project_id}",
            "url": f"{self.settings.base_url}/ja/grant/KAKENHI-PROJECT-{project_id}/",
        }

        # Title
        title_elem = soup.find("h1")
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # Remove "KAKEN — " prefix if present
            title_text = re.sub(r"^KAKEN\s*[—–-]\s*", "", title_text)
            project["title"] = title_text

        # Parse table rows (th: label, td: value)
        field_mapping = {
            "研究種目": "research_category",
            "研究機関": "institution",
            "研究代表者": "principal_investigator",
            "研究期間": "fiscal_years",
            "配分額": "budget_text",
            "キーワード": "keywords_text",
            "研究概要": "summary",
            "研究開始時の研究の概要": "summary",
            "審査区分": "review_section",
            "研究分野": "research_field",
            "研究課題ステータス": "status",
        }

        for row in soup.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                label = th.get_text(strip=True)
                value = td.get_text(strip=True)

                # Match label to field
                for key_pattern, field_name in field_mapping.items():
                    if key_pattern in label:
                        if field_name == "keywords_text":
                            # Parse keywords
                            keywords = [k.strip() for k in re.split(r"[/／、,]", value)]
                            project["keywords"] = [k for k in keywords if k]
                        elif field_name == "budget_text":
                            # Parse budget - extract total amount
                            budget_match = re.search(r"([\d,]+)千円", value)
                            if budget_match:
                                # Convert from thousands to yen
                                project["total_budget"] = (
                                    int(budget_match.group(1).replace(",", "")) * 1000
                                )
                        elif field_name == "fiscal_years":
                            # Parse fiscal years
                            project["fiscal_years"] = value
                            year_match = re.search(r"(\d{4})", value)
                            if year_match:
                                project["fiscal_year_start"] = int(year_match.group(1))
                            end_match = re.search(r"[–-]\s*(\d{4})", value)
                            if end_match:
                                project["fiscal_year_end"] = int(end_match.group(1))
                        elif field_name == "summary":
                            project["summary"] = value[:1000]
                        else:
                            project[field_name] = value
                        break

        return project

    def _parse_researcher_results(self, html: str) -> dict[str, Any]:
        """Parse researcher search results HTML.

        Args:
            html: HTML response text

        Returns:
            Parsed results as dictionary
        """
        soup = BeautifulSoup(html, "lxml")
        researchers: list[dict[str, Any]] = []

        # Find total count - "検索結果: X件" format
        total_count = 0
        for text in soup.find_all(string=re.compile(r"[\d,]+件")):
            text_str = str(text)
            match = re.search(r"([\d,]+)件", text_str)
            if match:
                total_count = int(match.group(1).replace(",", ""))
                break

        # Parse researcher entries - look for links to /nrid/ pages
        seen_ids: set[str] = set()
        for link in soup.find_all("a", href=re.compile(r"/nrid/")):
            href = str(link.get("href", ""))
            # Extract researcher number from URL
            nrid_match = re.search(r"/nrid/(\d+)/", href)
            if not nrid_match:
                continue

            researcher_number = nrid_match.group(1)
            # Remove leading 1000 prefix if present
            if researcher_number.startswith("1000"):
                researcher_number = researcher_number[4:]

            # Skip duplicates
            if researcher_number in seen_ids:
                continue
            seen_ids.add(researcher_number)

            # Get researcher name from link text
            # Format: "山田 太郎  Yamada Taro  (12345678)"
            name_text = link.get_text(strip=True)

            # Extract Japanese name - characters before romanization
            # Japanese name ends where ASCII letters begin
            jp_name_match = re.match(r"([\u3000-\u9fff\s]+)", name_text)
            if jp_name_match:
                name = jp_name_match.group(1).strip()
            else:
                # Fallback: take first two space-separated parts
                parts = name_text.split()
                name = " ".join(parts[:2]) if len(parts) >= 2 else parts[0]

            researcher: dict[str, Any] = {
                "researcher_number": researcher_number,
                "name": name,
                "url": f"{self.settings.researcher_base_url}{href}",
            }

            # Try to get affiliation from parent elements
            parent = link.find_parent("li") or link.find_parent("div")
            if parent:
                parent_text = parent.get_text(" ", strip=True)
                # Look for affiliation pattern after the name
                aff_match = re.search(r"(?:所属|機関)[：:]?\s*(.+?)(?:\s|$)", parent_text)
                if aff_match:
                    researcher["affiliation"] = aff_match.group(1)

            researchers.append(researcher)

        return {
            "total_count": total_count,
            "researchers": researchers,
        }
