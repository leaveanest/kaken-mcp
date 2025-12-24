"""Researcher search tools for KAKEN MCP."""

from typing import Any

from fastmcp import FastMCP

from kaken_mcp.client import KakenApiError, KakenClient
from kaken_mcp.config import Settings


def register_researcher_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register researcher-related tools.

    Args:
        mcp: FastMCP server instance
        settings: Application settings
    """

    @mcp.tool()
    async def search_researchers(
        name: str | None = None,
        researcher_number: str | None = None,
        institution: str | None = None,
        research_field: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for researchers in the KAKEN database.

        This tool searches for researchers who have received Grants-in-Aid
        for Scientific Research (KAKENHI) funding.

        Args:
            name: Researcher name (partial match supported, use * for wildcard)
            researcher_number: Unique researcher number
            institution: Research institution or university name
            research_field: Research field or discipline
            limit: Maximum number of results to return (default: 20, max: 200)
            offset: Starting position for pagination (default: 0)

        Returns:
            Dictionary containing:
            - total_count: Total number of matching researchers
            - researchers: List of researcher summaries (name, researcher_number, etc.)
        """
        async with KakenClient(settings) as client:
            try:
                result = await client.search_researchers(
                    name=name,
                    researcher_number=researcher_number,
                    institution=institution,
                    research_field=research_field,
                    limit=limit,
                    offset=offset,
                )
                return result
            except KakenApiError as e:
                return {"error": str(e), "total_count": 0, "researchers": []}
