"""Research project search tools for KAKEN MCP."""

from typing import Any

from fastmcp import FastMCP

from kaken_mcp.client import KakenClient, KakenError
from kaken_mcp.config import Settings


def register_project_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register project-related tools.

    Args:
        mcp: FastMCP server instance
        settings: Application settings
    """

    @mcp.tool()
    async def search_projects(
        keyword: str | None = None,
        title: str | None = None,
        researcher_name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        fiscal_year_from: int | None = None,
        fiscal_year_to: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for research projects in the KAKEN database.

        This tool searches the Grants-in-Aid for Scientific Research (KAKENHI)
        database for research projects matching the specified criteria.

        Args:
            keyword: Free text search across all fields
            title: Research project title (partial match)
            researcher_name: Name of a researcher involved in the project
            researcher_number: Unique researcher number
            institution: Research institution name
            research_field: Research field or discipline
            fiscal_year_from: Start of fiscal year range (e.g., 2020)
            fiscal_year_to: End of fiscal year range (e.g., 2024)
            limit: Maximum number of results to return (default: 20, max: 200)
            offset: Starting position for pagination (default: 0)

        Returns:
            Dictionary containing:
            - total_count: Total number of matching projects
            - projects: List of project summaries with id, title, principal_investigator, url
        """
        async with KakenClient(settings) as client:
            try:
                result = await client.search_projects(
                    keyword=keyword,
                    title=title,
                    researcher_name=researcher_name,
                    researcher_number=researcher_number,
                    institution=institution,
                    research_field=research_field,
                    fiscal_year_from=fiscal_year_from,
                    fiscal_year_to=fiscal_year_to,
                    limit=limit,
                    offset=offset,
                )
                return result
            except KakenError as e:
                return {"error": str(e), "total_count": 0, "projects": []}

    @mcp.tool()
    async def get_project_detail(project_id: str) -> dict[str, Any]:
        """Get detailed information about a specific research project.

        Retrieves comprehensive information about a research project including
        title, researchers, abstract, funding, and related publications.

        Args:
            project_id: Research project ID (e.g., "KAKENHI-PROJECT-19H00000" or "19H00000")

        Returns:
            Dictionary containing project details:
            - id: Project identifier
            - title: Project title
            - principal_investigator: Lead researcher name
            - researchers: List of all researchers involved
            - summary: Project summary/abstract
            - keywords: Research keywords
            - url: Link to the project page on KAKEN website
        """
        async with KakenClient(settings) as client:
            try:
                result = await client.get_project_detail(project_id)
                return result
            except KakenError as e:
                return {"error": str(e)}

    @mcp.tool()
    async def get_researcher_projects(
        researcher_number: str,
        role: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get all research projects associated with a specific researcher.

        Retrieves the list of research projects where the specified researcher
        has been involved, optionally filtered by their role.

        Args:
            researcher_number: Unique researcher number (required)
            role: Filter by role - "principal" (lead) or "co-investigator"
            limit: Maximum number of results to return (default: 20, max: 200)
            offset: Starting position for pagination (default: 0)

        Returns:
            Dictionary containing:
            - total_count: Total number of matching projects
            - projects: List of project summaries
        """
        async with KakenClient(settings) as client:
            try:
                result = await client.get_researcher_projects(
                    researcher_number=researcher_number,
                    role=role,
                    limit=limit,
                    offset=offset,
                )
                return result
            except KakenError as e:
                return {"error": str(e), "total_count": 0, "projects": []}
