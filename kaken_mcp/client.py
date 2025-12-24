"""KAKEN API client for accessing research project and researcher data."""

from typing import Any
from xml.etree import ElementTree

import httpx

from kaken_mcp.config import Settings


class KakenApiError(Exception):
    """Exception raised when KAKEN API request fails."""

    pass


class KakenClient:
    """Client for KAKEN OpenSearch API."""

    # XML namespaces used in KAKEN API responses
    NAMESPACES = {
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "atom": "http://www.w3.org/2005/Atom",
        "kaken": "https://kaken.nii.ac.jp/ns/kaken/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    def __init__(self, settings: Settings) -> None:
        """Initialize the KAKEN API client.

        Args:
            settings: Application settings containing API credentials
        """
        self.settings = settings
        self._client = httpx.AsyncClient(timeout=settings.request_timeout)

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
        """Search for research projects.

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
        params: dict[str, str] = {
            "appid": self.settings.app_id,
            "format": "xml",
        }

        # Add search parameters
        if keyword:
            params["q"] = keyword
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
            params["st"] = str(offset + 1)  # KAKEN uses 1-based indexing

        response = await self._request(self.settings.project_api_url, params)
        return self._parse_project_response(response)

    async def get_project_detail(self, project_id: str) -> dict[str, Any]:
        """Get detailed information for a specific research project.

        Args:
            project_id: Research project ID (e.g., "KAKENHI-PROJECT-19H00000")

        Returns:
            Dictionary containing project details
        """
        # Extract numeric ID if full format is provided
        numeric_id = project_id
        if "KAKENHI-PROJECT-" in project_id:
            numeric_id = project_id.replace("KAKENHI-PROJECT-", "")

        params: dict[str, str] = {
            "appid": self.settings.app_id,
            "format": "xml",
            "q10": numeric_id,  # Project number search
        }

        response = await self._request(self.settings.project_api_url, params)
        result = self._parse_project_response(response)

        if result["projects"]:
            return result["projects"][0]
        raise KakenApiError(f"Project not found: {project_id}")

    async def search_researchers(
        self,
        name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for researchers.

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
        params: dict[str, str] = {
            "appid": self.settings.app_id,
            "format": "xml",
        }

        # Build query string
        query_parts: list[str] = []
        if name:
            query_parts.append(name)
        if researcher_number:
            params["qn"] = researcher_number
        if institution:
            query_parts.append(institution)
        if research_field:
            query_parts.append(research_field)

        if query_parts:
            params["qm"] = " ".join(query_parts)

        # Pagination
        actual_limit = min(limit or self.settings.default_limit, self.settings.max_limit)
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        response = await self._request(self.settings.researcher_api_url, params)
        return self._parse_researcher_response(response)

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
        params: dict[str, str] = {
            "appid": self.settings.app_id,
            "format": "xml",
            "q15": researcher_number,
        }

        if role:
            if role.lower() in ["principal", "代表者", "研究代表者"]:
                params["q13"] = "1"  # Principal investigator
            elif role.lower() in ["co-investigator", "分担者", "研究分担者"]:
                params["q13"] = "2"  # Co-investigator

        actual_limit = min(limit or self.settings.default_limit, self.settings.max_limit)
        params["rw"] = str(actual_limit)
        if offset > 0:
            params["st"] = str(offset + 1)

        response = await self._request(self.settings.project_api_url, params)
        return self._parse_project_response(response)

    async def _request(self, url: str, params: dict[str, str]) -> str:
        """Make an HTTP request to the API.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Response text

        Raises:
            KakenApiError: If the request fails
        """
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise KakenApiError(f"API request failed with status {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise KakenApiError(f"API request failed: {e}") from e

    def _parse_project_response(self, xml_text: str) -> dict[str, Any]:
        """Parse XML response for project search.

        Args:
            xml_text: XML response text

        Returns:
            Parsed response as dictionary
        """
        root = ElementTree.fromstring(xml_text)

        # Get total results
        total_elem = root.find(".//opensearch:totalResults", self.NAMESPACES)
        total_count = int(total_elem.text) if total_elem is not None and total_elem.text else 0

        projects: list[dict[str, Any]] = []

        # Parse each entry
        for entry in root.findall(".//atom:entry", self.NAMESPACES):
            project = self._parse_project_entry(entry)
            if project:
                projects.append(project)

        return {
            "total_count": total_count,
            "projects": projects,
        }

    def _parse_project_entry(self, entry: ElementTree.Element) -> dict[str, Any]:
        """Parse a single project entry from XML.

        Args:
            entry: XML entry element

        Returns:
            Project data as dictionary
        """
        project: dict[str, Any] = {}

        # Title
        title_elem = entry.find("atom:title", self.NAMESPACES)
        if title_elem is not None and title_elem.text:
            project["title"] = title_elem.text

        # Link/URL
        link_elem = entry.find("atom:link[@rel='alternate']", self.NAMESPACES)
        if link_elem is not None:
            project["url"] = link_elem.get("href", "")

        # ID from link
        if "url" in project:
            url = project["url"]
            if "/grant/" in url:
                parts = url.rstrip("/").split("/")
                if parts:
                    project["id"] = parts[-1]

        # Author/Principal Investigator
        author_elem = entry.find("atom:author/atom:name", self.NAMESPACES)
        if author_elem is not None and author_elem.text:
            project["principal_investigator"] = author_elem.text

        # Summary
        summary_elem = entry.find("atom:summary", self.NAMESPACES)
        if summary_elem is not None and summary_elem.text:
            project["summary"] = summary_elem.text

        # Dublin Core elements
        for dc_elem in entry.findall("dc:*", self.NAMESPACES):
            tag = dc_elem.tag.replace("{http://purl.org/dc/elements/1.1/}", "")
            if dc_elem.text:
                if tag == "creator":
                    project.setdefault("researchers", []).append(dc_elem.text)
                elif tag == "subject":
                    project.setdefault("keywords", []).append(dc_elem.text)
                elif tag == "description":
                    project["description"] = dc_elem.text
                elif tag == "date":
                    project["date"] = dc_elem.text

        return project

    def _parse_researcher_response(self, xml_text: str) -> dict[str, Any]:
        """Parse XML response for researcher search.

        Args:
            xml_text: XML response text

        Returns:
            Parsed response as dictionary
        """
        root = ElementTree.fromstring(xml_text)

        # Get total results
        total_elem = root.find(".//opensearch:totalResults", self.NAMESPACES)
        total_count = int(total_elem.text) if total_elem is not None and total_elem.text else 0

        researchers: list[dict[str, Any]] = []

        # Parse each entry
        for entry in root.findall(".//atom:entry", self.NAMESPACES):
            researcher = self._parse_researcher_entry(entry)
            if researcher:
                researchers.append(researcher)

        return {
            "total_count": total_count,
            "researchers": researchers,
        }

    def _parse_researcher_entry(self, entry: ElementTree.Element) -> dict[str, Any]:
        """Parse a single researcher entry from XML.

        Args:
            entry: XML entry element

        Returns:
            Researcher data as dictionary
        """
        researcher: dict[str, Any] = {}

        # Name
        title_elem = entry.find("atom:title", self.NAMESPACES)
        if title_elem is not None and title_elem.text:
            researcher["name"] = title_elem.text

        # Link/URL
        link_elem = entry.find("atom:link[@rel='alternate']", self.NAMESPACES)
        if link_elem is not None:
            researcher["url"] = link_elem.get("href", "")

        # Researcher number from URL
        if "url" in researcher:
            url = researcher["url"]
            parts = url.rstrip("/").split("/")
            if parts:
                researcher["researcher_number"] = parts[-1]

        # Summary (often contains affiliation info)
        summary_elem = entry.find("atom:summary", self.NAMESPACES)
        if summary_elem is not None and summary_elem.text:
            researcher["affiliation"] = summary_elem.text

        return researcher
