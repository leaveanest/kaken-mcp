"""MCP tools for KAKEN database access."""

from fastmcp import FastMCP

from kaken_mcp.config import Settings
from kaken_mcp.tools.projects import register_project_tools
from kaken_mcp.tools.researchers import register_researcher_tools


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register all KAKEN MCP tools.

    Args:
        mcp: FastMCP server instance
        settings: Application settings
    """
    register_project_tools(mcp, settings)
    register_researcher_tools(mcp, settings)


__all__ = ["register_tools"]
