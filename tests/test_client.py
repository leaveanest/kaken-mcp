"""Tests for KAKEN client."""

import pytest
from unittest.mock import AsyncMock, patch

from kaken_mcp.client import KakenClient, KakenError
from kaken_mcp.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings()


@pytest.fixture
def sample_search_html() -> str:
    """Sample HTML response for project search."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>KAKEN — 検索結果</title></head>
    <body>
        <div class="result-count"><strong>9,898</strong>件</div>
        <div class="search-result-item">
            <h3><a href="/ja/grant/KAKENHI-PROJECT-19H00001/">人工知能を用いた研究課題分析</a></h3>
            <h4>山田太郎, 東京大学, 教授</h4>
            <p>研究期間 (年度) 2019 – 2023</p>
            <p>配分額: ¥10,000,000</p>
        </div>
        <div class="search-result-item">
            <h3><a href="/ja/grant/KAKENHI-PROJECT-20K00002/">機械学習の応用研究</a></h3>
            <h4>鈴木花子, 京都大学, 准教授</h4>
            <p>研究期間 (年度) 2020 – 2024</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_detail_html() -> str:
    """Sample HTML response for project detail."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>KAKEN — 人工知能を用いた研究課題分析</title></head>
    <body>
        <main>
            <h1>人工知能を用いた研究課題分析</h1>
            <table>
                <tr><th>研究種目</th><td>基盤研究(A)</td></tr>
                <tr><th>研究代表者</th><td>山田太郎 東京大学, 教授</td></tr>
                <tr><th>研究機関</th><td>東京大学</td></tr>
                <tr><th>研究期間 (年度)</th><td>2019-04-01 – 2023-03-31</td></tr>
                <tr><th>配分額</th><td>10,000千円 (直接経費: 8,000千円)</td></tr>
                <tr><th>キーワード</th><td>人工知能 / 機械学習 / データ分析</td></tr>
                <tr><th>研究概要</th><td>本研究では人工知能技術を用いて研究課題を分析し...</td></tr>
            </table>
        </main>
    </body>
    </html>
    """


@pytest.fixture
def sample_researcher_html() -> str:
    """Sample HTML response for researcher search."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>KAKEN — 研究者検索結果</title></head>
    <body>
        <div>検索結果: 150件 / 山田</div>
        <div class="search-result-item">
            <h3 class="item_mainTitle">
                <div class="title"><a href="/ja/nrid/1000000000001/">山田 太郎  Yamada Taro  (00000001)</a></div>
            </h3>
            <p>東京大学 情報理工学系研究科 教授</p>
        </div>
    </body>
    </html>
    """


class TestKakenClient:
    """Tests for KakenClient class."""

    async def test_search_projects_success(
        self, settings: Settings, sample_search_html: str
    ) -> None:
        """Test successful project search."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_search_html
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                result = await client.search_projects(keyword="人工知能")

            assert result["total_count"] == 9898
            assert len(result["projects"]) == 2
            assert result["projects"][0]["title"] == "人工知能を用いた研究課題分析"
            assert result["projects"][0]["id"] == "KAKENHI-PROJECT-19H00001"

    async def test_search_projects_with_pagination(
        self, settings: Settings, sample_search_html: str
    ) -> None:
        """Test project search with pagination parameters."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_search_html
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                await client.search_projects(keyword="test", limit=50, offset=100)

            # Verify pagination params were passed
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["rw"] == "50"
            assert params["st"] == "101"  # 1-based indexing

    async def test_get_project_detail_success(
        self, settings: Settings, sample_detail_html: str
    ) -> None:
        """Test successful project detail retrieval."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_detail_html
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                result = await client.get_project_detail("19H00001")

            assert result["id"] == "KAKENHI-PROJECT-19H00001"
            assert "人工知能" in result["title"]
            assert result["research_category"] == "基盤研究(A)"
            assert "人工知能" in result.get("keywords", [])

    async def test_search_researchers_success(
        self, settings: Settings, sample_researcher_html: str
    ) -> None:
        """Test successful researcher search."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_researcher_html
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                result = await client.search_researchers(name="山田")

            assert result["total_count"] == 150
            assert len(result["researchers"]) == 1
            assert result["researchers"][0]["name"] == "山田 太郎"
            assert result["researchers"][0]["researcher_number"] == "000000001"

    async def test_get_researcher_projects_with_role(
        self, settings: Settings, sample_search_html: str
    ) -> None:
        """Test getting researcher projects filtered by role."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_search_html
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                await client.get_researcher_projects("12345678", role="principal")

            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["qm"] == "12345678"
            assert params["c2[]"] == "principal_investigator"


class TestParseSearchResults:
    """Tests for search results parsing."""

    def test_parse_empty_results(self, settings: Settings) -> None:
        """Test parsing empty search results."""
        client = KakenClient(settings)
        html = """
        <!DOCTYPE html>
        <html><body>
            <p>見つかりませんでした。</p>
        </body></html>
        """
        result = client._parse_search_results(html)
        assert result["total_count"] == 0
        assert result["projects"] == []

    def test_parse_project_id_from_url(self, settings: Settings) -> None:
        """Test extracting project ID from URL."""
        client = KakenClient(settings)
        html = """
        <!DOCTYPE html>
        <html><body>
            <h3><a href="/ja/grant/KAKENHI-PROJECT-21K18343/">Test Project</a></h3>
        </body></html>
        """
        result = client._parse_search_results(html)
        assert len(result["projects"]) == 1
        assert result["projects"][0]["id"] == "KAKENHI-PROJECT-21K18343"


class TestParseProjectDetail:
    """Tests for project detail parsing."""

    def test_parse_keywords(self, settings: Settings) -> None:
        """Test parsing keywords from detail page."""
        client = KakenClient(settings)
        html = """
        <!DOCTYPE html>
        <html><body><main>
            <h1>テスト研究</h1>
            <table>
                <tr><th>キーワード</th><td>AI / 機械学習 / データ</td></tr>
            </table>
        </main></body></html>
        """
        result = client._parse_project_detail(html, "12345678")
        assert "AI" in result.get("keywords", [])
        assert "機械学習" in result.get("keywords", [])

    def test_parse_budget(self, settings: Settings) -> None:
        """Test parsing budget from detail page."""
        client = KakenClient(settings)
        html = """
        <!DOCTYPE html>
        <html><body><main>
            <h1>テスト研究</h1>
            <table>
                <tr><th>配分額</th><td>15,000千円 (直接経費: 12,000千円)</td></tr>
            </table>
        </main></body></html>
        """
        result = client._parse_project_detail(html, "12345678")
        assert result["total_budget"] == 15000000
