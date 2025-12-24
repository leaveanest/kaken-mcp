"""Tests for KAKEN API client."""

import pytest
from unittest.mock import AsyncMock, patch

from kaken_mcp.client import KakenClient, KakenApiError
from kaken_mcp.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        app_id="test_app_id",
        project_api_url="https://kaken.nii.ac.jp/opensearch/",
        researcher_api_url="https://nrid.nii.ac.jp/opensearch/",
    )


@pytest.fixture
def sample_project_xml() -> str:
    """Sample XML response for project search."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
          xmlns:dc="http://purl.org/dc/elements/1.1/">
        <opensearch:totalResults>1</opensearch:totalResults>
        <opensearch:startIndex>1</opensearch:startIndex>
        <opensearch:itemsPerPage>20</opensearch:itemsPerPage>
        <entry>
            <title>人工知能を用いた研究課題分析</title>
            <link rel="alternate" href="https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-19H00001/"/>
            <author>
                <name>山田太郎</name>
            </author>
            <summary>本研究では人工知能技術を用いて...</summary>
            <dc:creator>山田太郎</dc:creator>
            <dc:subject>人工知能</dc:subject>
            <dc:subject>機械学習</dc:subject>
        </entry>
    </feed>
    """


@pytest.fixture
def sample_researcher_xml() -> str:
    """Sample XML response for researcher search."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
        <opensearch:totalResults>1</opensearch:totalResults>
        <opensearch:startIndex>1</opensearch:startIndex>
        <opensearch:itemsPerPage>20</opensearch:itemsPerPage>
        <entry>
            <title>山田太郎</title>
            <link rel="alternate" href="https://nrid.nii.ac.jp/ja/nrid/1000000000001/"/>
            <summary>東京大学 情報理工学系研究科 教授</summary>
        </entry>
    </feed>
    """


class TestKakenClient:
    """Tests for KakenClient class."""

    async def test_search_projects_success(
        self, settings: Settings, sample_project_xml: str
    ) -> None:
        """Test successful project search."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_project_xml
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                result = await client.search_projects(keyword="人工知能")

            assert result["total_count"] == 1
            assert len(result["projects"]) == 1
            assert result["projects"][0]["title"] == "人工知能を用いた研究課題分析"
            assert result["projects"][0]["principal_investigator"] == "山田太郎"
            assert "人工知能" in result["projects"][0].get("keywords", [])

    async def test_search_projects_with_pagination(self, settings: Settings) -> None:
        """Test project search with pagination parameters."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom"
                  xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
                <opensearch:totalResults>0</opensearch:totalResults>
            </feed>
            """
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                await client.search_projects(keyword="test", limit=50, offset=100)

            # Verify pagination params were passed
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["rw"] == "50"
            assert params["st"] == "101"  # 1-based indexing

    async def test_search_researchers_success(
        self, settings: Settings, sample_researcher_xml: str
    ) -> None:
        """Test successful researcher search."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = sample_researcher_xml
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                result = await client.search_researchers(name="山田")

            assert result["total_count"] == 1
            assert len(result["researchers"]) == 1
            assert result["researchers"][0]["name"] == "山田太郎"
            assert "東京大学" in result["researchers"][0].get("affiliation", "")

    async def test_get_project_detail_not_found(self, settings: Settings) -> None:
        """Test project detail when project is not found."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom"
                  xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
                <opensearch:totalResults>0</opensearch:totalResults>
            </feed>
            """
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                with pytest.raises(KakenApiError, match="Project not found"):
                    await client.get_project_detail("KAKENHI-PROJECT-99999999")

    async def test_get_researcher_projects_with_role(self, settings: Settings) -> None:
        """Test getting researcher projects filtered by role."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom"
                  xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
                <opensearch:totalResults>0</opensearch:totalResults>
            </feed>
            """
            mock_response.raise_for_status = lambda: None
            mock_get.return_value = mock_response

            async with KakenClient(settings) as client:
                await client.get_researcher_projects("12345678", role="principal")

            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["q15"] == "12345678"
            assert params["q13"] == "1"  # Principal investigator


class TestParseProjectEntry:
    """Tests for project entry parsing."""

    def test_parse_project_id_from_url(self, settings: Settings) -> None:
        """Test extracting project ID from URL."""
        client = KakenClient(settings)
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
            <opensearch:totalResults>1</opensearch:totalResults>
            <entry>
                <title>Test Project</title>
                <link rel="alternate" href="https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-19H00001/"/>
            </entry>
        </feed>
        """
        result = client._parse_project_response(xml_text)
        assert result["projects"][0]["id"] == "KAKENHI-PROJECT-19H00001"
