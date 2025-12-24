"""KAKEN client for scraping research project and researcher data from website."""

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from kaken_mcp.config import Settings


class KakenError(Exception):
    """Exception raised when KAKEN request fails."""

    pass


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
            },
            follow_redirects=True,
        )

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

        # Pagination
        actual_limit = min(limit or self.settings.default_limit, self.settings.max_limit)
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.base_url}/ja/search/"
        html = await self._request(url, params)
        return self._parse_search_results(html)

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

        # Build query
        query_parts: list[str] = []
        if name:
            query_parts.append(name)
        if institution:
            query_parts.append(institution)
        if research_field:
            query_parts.append(research_field)

        if query_parts:
            params["qm"] = " ".join(query_parts)
        if researcher_number:
            params["qn"] = researcher_number

        # Pagination
        actual_limit = min(limit or self.settings.default_limit, self.settings.max_limit)
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.researcher_base_url}/ja/search/"
        html = await self._request(url, params)
        return self._parse_researcher_results(html)

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

        actual_limit = min(limit or self.settings.default_limit, self.settings.max_limit)
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        url = f"{self.settings.base_url}/ja/search/"
        html = await self._request(url, params)
        return self._parse_search_results(html)

    async def _request(
        self, url: str, params: dict[str, str] | None = None
    ) -> str:
        """Make an HTTP request.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            Response HTML text

        Raises:
            KakenError: If the request fails
        """
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise KakenError(f"Request failed with status {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise KakenError(f"Request failed: {e}") from e

    def _parse_search_results(self, html: str) -> dict[str, Any]:
        """Parse search results HTML.

        Args:
            html: HTML response text

        Returns:
            Parsed results as dictionary
        """
        soup = BeautifulSoup(html, "lxml")
        projects: list[dict[str, Any]] = []

        # Find total count
        total_count = 0
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
        title_elem = soup.find("h1") or soup.find("title")
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # Remove "KAKEN — " prefix if present
            title_text = re.sub(r"^KAKEN\s*[—–-]\s*", "", title_text)
            project["title"] = title_text

        # Get all text content for parsing
        main_content = soup.find("main") or soup.find("article") or soup.body
        if not main_content:
            return project

        full_text = main_content.get_text()

        # Research category
        category_match = re.search(r"研究種目[：:]\s*(.+?)(?:\n|$)", full_text)
        if category_match:
            project["research_category"] = category_match.group(1).strip()

        # Principal investigator
        pi_match = re.search(r"研究代表者[：:]\s*(.+?)(?:\s+\(|$|\n)", full_text)
        if pi_match:
            project["principal_investigator"] = pi_match.group(1).strip()

        # Institution
        inst_match = re.search(r"研究機関[：:]\s*(.+?)(?:\n|$)", full_text)
        if inst_match:
            project["institution"] = inst_match.group(1).strip()

        # Research period
        period_pattern = r"研究期間[^：:]*[：:]\s*(\d{4})[^\d]*[-–～~][^\d]*(\d{4})?"
        period_match = re.search(period_pattern, full_text)
        if period_match:
            project["fiscal_year_start"] = int(period_match.group(1))
            if period_match.group(2):
                project["fiscal_year_end"] = int(period_match.group(2))

        # Budget
        budget_match = re.search(r"配分額[^：:]*[：:]\s*[¥￥]?\s*([\d,]+)", full_text)
        if budget_match:
            project["total_budget"] = int(budget_match.group(1).replace(",", ""))

        # Keywords
        keywords_match = re.search(r"キーワード[：:]\s*(.+?)(?:\n|研究)", full_text)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            keywords = [k.strip() for k in re.split(r"[/／、,]", keywords_text)]
            project["keywords"] = [k for k in keywords if k]

        # Research summary/abstract
        summary_pattern = r"研究概要[^：:]*[：:]\s*(.+?)(?:キーワード|研究成果|$)"
        summary_match = re.search(summary_pattern, full_text, re.DOTALL)
        if summary_match:
            project["summary"] = summary_match.group(1).strip()[:1000]

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

        # Find total count
        total_count = 0
        count_elem = soup.select_one(".search-result-count, .result-count, strong")
        if count_elem:
            count_text = count_elem.get_text()
            numbers = re.findall(r"[\d,]+", count_text)
            if numbers:
                total_count = int(numbers[0].replace(",", ""))

        # Parse researcher entries
        entries = soup.select(".search-result-item, .result-item, article")

        if not entries:
            # Fallback: look for links to researcher pages
            for link in soup.find_all("a", href=re.compile(r"/nrid/")):
                researcher = self._parse_researcher_from_list(link.parent or link)
                if researcher:
                    researchers.append(researcher)
        else:
            for entry in entries:
                researcher = self._parse_researcher_from_list(entry)
                if researcher:
                    researchers.append(researcher)

        return {
            "total_count": total_count,
            "researchers": researchers,
        }

    def _parse_researcher_from_list(self, element: Tag) -> dict[str, Any] | None:
        """Parse a single researcher entry from search results.

        Args:
            element: BeautifulSoup element containing researcher info

        Returns:
            Researcher data as dictionary or None if parsing fails
        """
        researcher: dict[str, Any] = {}

        # Find name and URL
        name_link = element.find("a", href=re.compile(r"/nrid/"))
        if name_link:
            researcher["name"] = name_link.get_text(strip=True)
            href_attr = name_link.get("href", "")
            href = str(href_attr) if href_attr else ""
            if href:
                if href.startswith("/"):
                    researcher["url"] = f"{self.settings.researcher_base_url}{href}"
                else:
                    researcher["url"] = href
                # Extract researcher number from URL
                match = re.search(r"/nrid/(\d+)", href)
                if match:
                    researcher["researcher_number"] = match.group(1)

        if not researcher.get("name"):
            return None

        # Find affiliation info
        text = element.get_text()
        # Try to extract institution from text
        inst_match = re.search(r"(大学|研究所|研究機構|センター|機構)", text)
        if inst_match:
            # Get surrounding context
            start = max(0, inst_match.start() - 20)
            end = min(len(text), inst_match.end() + 10)
            researcher["affiliation"] = text[start:end].strip()

        return researcher
