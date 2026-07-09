"""MCP tools for KAKEN database access."""

from fastmcp import FastMCP

from kaken_mcp.client import KakenClient
from kaken_mcp.tools.projects import register_project_tools
from kaken_mcp.tools.researchers import register_researcher_tools


def register_tools(mcp: FastMCP, client: KakenClient) -> None:
    """Register all KAKEN MCP tools.

    Args:
        mcp: FastMCP server instance
        client: Shared KAKEN client used by all tools
    """
    register_project_tools(mcp, client)
    register_researcher_tools(mcp, client)


__all__ = ["register_tools"]
