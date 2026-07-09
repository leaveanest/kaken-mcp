"""Tests for MCP server wiring."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from kaken_mcp.client import KakenClient
from kaken_mcp.server import create_server


class TestServerInstructions:
    """Tests for the server instructions text."""

    def test_do_not_mention_nonexistent_app_id(self) -> None:
        """Instructions must not require a config option that does not exist."""
        server = create_server()
        assert "KAKEN_APP_ID" not in (server.instructions or "")


class TestSharedClient:
    """Tests for KakenClient lifecycle across tool calls."""

    async def test_tool_calls_reuse_one_kaken_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All tool invocations share one KakenClient so rate limiting applies."""
        monkeypatch.setenv("KAKEN_REQUEST_DELAY", "0.01")

        init_calls = 0
        original_init = KakenClient.__init__

        def counting_init(self: KakenClient, *args: Any, **kwargs: Any) -> None:
            nonlocal init_calls
            init_calls += 1
            original_init(self, *args, **kwargs)

        html = "<html><body><p>見つかりませんでした。</p></body></html>"
        with patch.object(KakenClient, "__init__", counting_init):
            server = create_server()
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = AsyncMock()
                mock_response.text = html
                mock_response.raise_for_status = lambda: None
                mock_get.return_value = mock_response

                async with Client(server) as client:
                    await client.call_tool("search_projects", {"keyword": "AI"})
                    await client.call_tool("search_projects", {"keyword": "ML"})

        assert init_calls == 1

    async def test_server_survives_second_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tools must keep working when the server is opened a second time.

        The fake get honours the real closed state of the underlying httpx
        client, like httpx itself does, so reusing a client closed by the
        first session's lifespan shutdown fails loudly here.
        """
        monkeypatch.setenv("KAKEN_REQUEST_DELAY", "0.01")
        server = create_server()

        mock_response = AsyncMock()
        mock_response.text = "<html><body><p>見つかりませんでした。</p></body></html>"
        mock_response.raise_for_status = lambda: None

        async def fake_get(self: Any, *args: Any, **kwargs: Any) -> Any:
            if self.is_closed:
                raise RuntimeError(
                    "Cannot send a request, as the client has been closed."
                )
            return mock_response

        with patch("httpx.AsyncClient.get", autospec=True, side_effect=fake_get):
            async with Client(server) as client:
                await client.call_tool("search_projects", {"keyword": "AI"})
            async with Client(server) as client:
                result = await client.call_tool("search_projects", {"keyword": "AI"})

        assert result.data.get("error") is None
