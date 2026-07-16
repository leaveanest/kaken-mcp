"""Tests for MCP server wiring."""

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client

from kaken_mcp.client import KakenClient
from kaken_mcp.server import create_server

EMPTY_PROJECT_XML = """<?xml version="1.0"?>
<grantAwardList xmlns="https://kaken.nii.ac.jp/xml/schemas/award/">
  <totalResults>0</totalResults><startIndex>1</startIndex><itemsPerPage>20</itemsPerPage>
</grantAwardList>
"""


def project_response() -> httpx.Response:
    """Build a valid empty project API response."""
    return httpx.Response(
        200,
        text=EMPTY_PROJECT_XML,
        headers={"content-type": "application/xml"},
        request=httpx.Request("GET", "https://kaken.nii.ac.jp/opensearch/"),
    )


class TestServerInstructions:
    """Tests for the server instructions text."""

    def test_mentions_required_app_id(self) -> None:
        """Instructions tell operators how to authenticate to the official API."""
        server = create_server()
        instructions = server.instructions or ""
        assert "OpenSearch API" in instructions
        assert "KAKEN_APP_ID" in instructions


class TestSharedClient:
    """Tests for KakenClient lifecycle across tool calls."""

    async def test_tool_calls_reuse_one_kaken_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All tool invocations share one KakenClient so rate limiting applies."""
        monkeypatch.setenv("KAKEN_REQUEST_DELAY", "0.01")
        monkeypatch.setenv("KAKEN_APP_ID", "test-app-id")

        init_calls = 0
        original_init = KakenClient.__init__

        def counting_init(self: KakenClient, *args: Any, **kwargs: Any) -> None:
            nonlocal init_calls
            init_calls += 1
            original_init(self, *args, **kwargs)

        with patch.object(KakenClient, "__init__", counting_init):
            server = create_server()
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_get.return_value = project_response()

                async with Client(server) as client:
                    await client.call_tool("search_projects", {"keyword": "AI"})
                    await client.call_tool("search_projects", {"keyword": "ML"})

        assert init_calls == 1

    async def test_server_survives_second_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tools must keep working when the server is opened a second time.

        The fake get honours the real closed state of the underlying httpx
        client, like httpx itself does, so reusing a client closed by the
        first session's lifespan shutdown fails loudly here.
        """
        monkeypatch.setenv("KAKEN_REQUEST_DELAY", "0.01")
        monkeypatch.setenv("KAKEN_APP_ID", "test-app-id")
        server = create_server()

        mock_response = project_response()

        async def fake_get(self: Any, *args: Any, **kwargs: Any) -> Any:
            if self.is_closed:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            return mock_response

        with patch("httpx.AsyncClient.get", autospec=True, side_effect=fake_get):
            async with Client(server) as client:
                await client.call_tool("search_projects", {"keyword": "AI"})
            async with Client(server) as client:
                result = await client.call_tool("search_projects", {"keyword": "AI"})

        assert result.data.get("error") is None
