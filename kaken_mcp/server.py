"""MCP server for KAKEN database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from kaken_mcp.client import KakenClient
from kaken_mcp.config import get_settings
from kaken_mcp.tools import register_tools


def create_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        Configured FastMCP server instance
    """
    settings = get_settings()

    # One shared client for all tool calls, so rate limiting and connection
    # pooling actually apply across requests.
    client = KakenClient(settings)

    @asynccontextmanager
    async def lifespan(app: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await client.close()

    mcp = FastMCP(
        name="kaken-mcp",
        instructions="""
KAKEN MCP server provides access to Japan's Grants-in-Aid for Scientific Research database.

Available tools:
- search_projects: Search for research projects by keyword, researcher, institution, etc.
- get_project_detail: Get detailed information about a specific research project
- search_researchers: Search for researchers by name, affiliation, or research field
- get_researcher_projects: Get all research projects for a specific researcher

No API key or registration is required; data is fetched from the public KAKEN website.
        """.strip(),
        lifespan=lifespan,
    )

    register_tools(mcp, client)

    return mcp


def main() -> None:
    """Main entry point for the MCP server."""
    server = create_server()
    server.run(show_banner=False)


if __name__ == "__main__":
    main()
