"""Unit tests for the official KAKEN OpenSearch client."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from kaken_mcp.client import KakenClient, KakenError
from kaken_mcp.config import Settings

PROJECT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<grantAwardList xmlns="https://kaken.nii.ac.jp/xml/schemas/award/">
  <grantAward id="19H00001" recordSet="kakenhi" awardNumber="19H00001">
    <urlList>
      <url xml:lang="en">https://kaken.nii.ac.jp/en/grant/KAKENHI-PROJECT-19H00001/</url>
      <url xml:lang="ja">https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-19H00001/</url>
    </urlList>
    <summary xml:lang="en"><title>English title</title></summary>
    <summary xml:lang="ja">
      <title>人工知能を用いた研究課題分析</title>
      <awardNumber awardNumber="19H00001" sequence="1" />
      <category>科学研究費助成事業</category><category>基盤研究(A)</category>
      <categoryFc>基盤研究(A)</categoryFc>
      <review_section>情報学基礎関連</review_section><field>情報学</field>
      <institution sequence="1">東京大学</institution>
      <member sequence="1" role="principal_investigator" researcherNumber="12345678">
        <affiliation><institution>東京大学</institution></affiliation>
        <personalName sequence="1"><fullName>山田 太郎</fullName></personalName>
      </member>
      <member sequence="2" role="co_investigator_buntan" researcherNumber="87654321">
        <personalName sequence="1"><fullName>鈴木 花子</fullName></personalName>
      </member>
      <projectStatus statusCode="granted" fiscalYear="2024" />
      <keywordList>
        <keyword sequence="1">人工知能</keyword><keyword sequence="2">機械学習</keyword>
      </keywordList>
      <paragraphList type="abstract" sequecne="1" parentId="x">
        <paragraph sequence="1">研究概要です。</paragraph>
      </paragraphList>
      <periodOfAward searchStartFiscalYear="2019" searchEndFiscalYear="2023">
        <startFiscalYear>2019</startFiscalYear><endFiscalYear>2023</endFiscalYear>
      </periodOfAward>
      <overallAwardAmount planned="false" sequence="2" caption="別通貨">
        <totalCost>99999999</totalCost>
      </overallAwardAmount>
      <overallAwardAmount planned="false" sequence="1" caption="総配分額">
        <directCost>8000000</directCost><indirectCost>2000000</indirectCost><totalCost>10000000</totalCost>
      </overallAwardAmount>
    </summary>
  </grantAward>
  <grantAward id="KAKENHI-PROJECT-20K00002" recordSet="kakenhi">
    <summary xml:lang="ja">
      <title>機械学習の応用研究</title>
      <periodOfAward searchStartFiscalYear="2020" searchEndFiscalYear="2024" />
    </summary>
  </grantAward>
  <totalResults>9898</totalResults><startIndex>1</startIndex><itemsPerPage>20</itemsPerPage>
</grantAwardList>
"""

RESEARCHER_JSON = json.dumps(
    {
        "researchers": [
            {
                "accn": "1000000000001",
                "recordSource": {"id:person:kakenhi": ["000000001"]},
                "id:person:erad": ["12345678"],
                "name": {
                    "humanReadableValue": [
                        {"lang": "en", "text": "Yamada Taro"},
                        {"lang": "ja", "text": "山田 太郎"},
                    ]
                },
                "affiliations:current": [
                    {
                        "sequence": 2,
                        "affiliation:institution": {
                            "humanReadableValue": [{"lang": "ja", "text": "旧大学"}]
                        },
                    },
                    {
                        "sequence": 1,
                        "affiliation:institution": {
                            "humanReadableValue": [{"lang": "ja", "text": "東京大学"}]
                        },
                        "affiliation:department": {
                            "humanReadableValue": [{"lang": "ja", "text": "情報理工学系研究科"}]
                        },
                        "affiliation:jobTitle": {
                            "humanReadableValue": [{"lang": "ja", "text": "教授"}]
                        },
                    },
                ],
            }
        ],
        "totalResults": 150,
        "startIndex": 1,
        "itemsPerPage": 20,
    },
    ensure_ascii=False,
)


@pytest.fixture
def settings() -> Settings:
    """Create API-enabled settings without rate-limit delays."""
    return Settings(app_id=SecretStr("test-app-id"), request_delay=0, retry_delay=0)


def response(body: str, content_type: str, status: int = 200) -> httpx.Response:
    """Build an HTTP response suitable for raise_for_status()."""
    request = httpx.Request("GET", "https://example.test/opensearch/")
    return httpx.Response(
        status, text=body, headers={"content-type": content_type}, request=request
    )


class TestProjectAPI:
    """Project endpoint and XML normalization tests."""

    async def test_search_projects_uses_documented_parameters(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml; charset=utf-8")
            async with KakenClient(settings) as client:
                result = await client.search_projects(
                    keyword="AI",
                    title="題名",
                    researcher_name="山田",
                    researcher_number="12345678",
                    institution="東京大学",
                    research_field="情報学",
                    fiscal_year_from=2019,
                    fiscal_year_to=2023,
                    limit=10,
                    offset=100,
                )

        _, kwargs = mock_get.call_args
        assert mock_get.call_args.args[0] == settings.project_api_url
        assert kwargs["params"] == {
            "appid": "test-app-id",
            "format": "xml",
            "lang": "ja",
            "rw": "20",
            "st": "101",
            "kw": "AI",
            "qa": "題名",
            "qg": "山田",
            "qm": "12345678",
            "qe": "東京大学",
            "qd": "情報学",
            "s1": "2019",
            "s2": "2023",
        }
        assert result["total_count"] == 9898
        assert result["projects"][0] == {
            "id": "KAKENHI-PROJECT-19H00001",
            "url": "https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-19H00001/",
            "title": "人工知能を用いた研究課題分析",
            "research_category": "基盤研究(A)",
            "institution": "東京大学",
            "principal_investigator": "山田 太郎",
            "researchers": [
                {
                    "name": "山田 太郎",
                    "role": "principal_investigator",
                    "researcher_number": "12345678",
                    "institution": "東京大学",
                },
                {
                    "name": "鈴木 花子",
                    "role": "co_investigator_buntan",
                    "researcher_number": "87654321",
                },
            ],
            "fiscal_year_start": 2019,
            "fiscal_year_end": 2023,
            "fiscal_years": "2019 - 2023",
            "status": "granted",
            "keywords": ["人工知能", "機械学習"],
            "summary": "研究概要です。",
            "review_section": "情報学基礎関連",
            "research_field": "情報学",
            "total_budget": 10000000,
        }
        assert result["projects"][1]["id"] == "KAKENHI-PROJECT-20K00002"
        assert result["projects"][1]["fiscal_year_start"] == 2020
        assert result["projects"][1]["fiscal_year_end"] == 2024

    @pytest.mark.parametrize(
        ("limit", "expected_rw"), [(1, "20"), (20, "20"), (21, "50"), (51, "100"), (101, "200")]
    )
    async def test_selects_smallest_supported_page_size(
        self, settings: Settings, limit: int, expected_rw: str
    ) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "text/xml")
            async with KakenClient(settings) as client:
                await client.search_projects(keyword="AI", limit=limit)
        assert mock_get.call_args.kwargs["params"]["rw"] == expected_rw

    async def test_limit_is_capped_at_mcp_max_and_sliced(self, settings: Settings) -> None:
        settings.max_limit = 1
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            async with KakenClient(settings) as client:
                result = await client.search_projects(keyword="AI", limit=500)
        assert mock_get.call_args.kwargs["params"]["rw"] == "20"
        assert len(result["projects"]) == 1

    async def test_limit_is_capped_at_api_maximum(self, settings: Settings) -> None:
        settings.max_limit = 1000
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            await KakenClient(settings).search_projects(keyword="AI", limit=600)
        assert mock_get.call_args.kwargs["params"]["rw"] == "500"

    async def test_period_falls_back_to_dates(self, settings: Settings) -> None:
        xml = """<grantAwardList>
          <grantAward awardNumber="21K00003"><summary xml:lang="ja">
            <title>日付だけの課題</title>
            <periodOfAward><startDate>2021-04-01</startDate><endDate>2025-03-31</endDate></periodOfAward>
          </summary></grantAward><totalResults>1</totalResults>
        </grantAwardList>"""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(xml, "application/xml")
            result = await KakenClient(settings).search_projects(keyword="日付")
        project = result["projects"][0]
        assert project["fiscal_year_start"] == 2021
        assert project["fiscal_year_end"] == 2024
        assert project["fiscal_years"] == "2021 - 2024"

    async def test_detail_searches_with_qb_and_keeps_legacy_shape(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            async with KakenClient(settings) as client:
                result = await client.get_project_detail("KAKENHI-PROJECT-19H00001")
        assert mock_get.call_args.kwargs["params"]["qb"] == "19H00001"
        assert result["id"] == "KAKENHI-PROJECT-19H00001"
        assert result["research_category"] == "基盤研究(A)"
        assert len(result["researchers"]) == 2

    async def test_detail_requires_an_exact_award_number_match(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            with pytest.raises(KakenError, match="Project not found"):
                await KakenClient(settings).get_project_detail("99Z99999")

    @pytest.mark.parametrize("project_id", ["19H00001/../x", "19H00001?x=1", "19H00001#x"])
    async def test_rejects_invalid_project_id(self, settings: Settings, project_id: str) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            async with KakenClient(settings) as client:
                with pytest.raises(KakenError, match="Invalid project ID"):
                    await client.get_project_detail(project_id)
        mock_get.assert_not_called()

    async def test_get_researcher_projects_maps_role(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            async with KakenClient(settings) as client:
                await client.get_researcher_projects("12345678", role="principal")
        params = mock_get.call_args.kwargs["params"]
        assert params["qm"] == "12345678"
        assert params["c2"] == "principal_investigator"


class TestResearcherAPI:
    """Researcher endpoint and JSON normalization tests."""

    async def test_search_researchers_uses_documented_parameters(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(RESEARCHER_JSON, "application/json")
            async with KakenClient(settings) as client:
                result = await client.search_researchers(
                    name="山田",
                    researcher_number="00000001",
                    institution="東京大学",
                    research_field="情報学",
                    limit=10,
                    offset=20,
                )

        assert mock_get.call_args.args[0] == settings.researcher_api_url
        assert mock_get.call_args.kwargs["params"] == {
            "appid": "test-app-id",
            "format": "json",
            "lang": "ja",
            "rw": "20",
            "st": "21",
            "qg": "山田",
            "qm": "00000001",
            "qh": "東京大学",
            "qd": "情報学",
        }
        assert result == {
            "total_count": 150,
            "researchers": [
                {
                    "researcher_number": "000000001",
                    "name": "山田 太郎",
                    "url": "https://nrid.nii.ac.jp/ja/nrid/1000000000001/",
                    "affiliation": "東京大学 情報理工学系研究科 教授",
                    "institution": "東京大学",
                    "department": "情報理工学系研究科",
                    "job_title": "教授",
                }
            ],
        }

    def test_researcher_number_and_url_fallbacks(self, settings: Settings) -> None:
        client = KakenClient(settings)
        result = client._parse_researcher(
            {
                "accn": "not-an-nrid",
                "id:person:erad": ["12345678"],
                "name": {"humanReadableValue": [{"lang": "ja", "text": "鈴木 花子"}]},
            }
        )
        assert result["researcher_number"] == "12345678"
        assert result["url"] == "https://nrid.nii.ac.jp/ja/nrid/100012345678/"

    def test_researcher_number_starting_with_1000_is_preserved(self, settings: Settings) -> None:
        result = KakenClient(settings)._parse_researcher(
            {
                "accn": "1000000000002",
                "recordSource": {"id:person:kakenhi": ["10001234"]},
                "name": {"humanReadableValue": [{"lang": "ja", "text": "高橋 一郎"}]},
            }
        )
        assert result["researcher_number"] == "10001234"
        assert result["url"] == "https://nrid.nii.ac.jp/ja/nrid/1000000000002/"


class TestErrorsAndLifecycle:
    """Credential, validation, retry, and shared-client behavior."""

    async def test_missing_app_id_fails_only_when_api_is_called(self) -> None:
        settings = Settings(app_id=None, request_delay=0)
        client = KakenClient(settings)
        with pytest.raises(KakenError, match="KAKEN_APP_ID is required"):
            await client.search_projects(keyword="AI")

    async def test_rejects_search_without_conditions(self, settings: Settings) -> None:
        client = KakenClient(settings)
        with pytest.raises(KakenError, match="project search condition"):
            await client.search_projects()
        with pytest.raises(KakenError, match="researcher search condition"):
            await client.search_researchers()

    async def test_rejects_inverted_fiscal_years(self, settings: Settings) -> None:
        with pytest.raises(KakenError, match="fiscal_year_from"):
            await KakenClient(settings).search_projects(fiscal_year_from=2025, fiscal_year_to=2024)

    @pytest.mark.parametrize(
        ("method", "offset", "maximum"),
        [("project", 200000, 200000), ("researcher", 1000, 1000)],
    )
    async def test_rejects_offset_past_api_maximum(
        self, settings: Settings, method: str, offset: int, maximum: int
    ) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            client = KakenClient(settings)
            with pytest.raises(KakenError, match=f"maximum start position of {maximum}"):
                if method == "project":
                    await client.search_projects(keyword="AI", offset=offset)
                else:
                    await client.search_researchers(name="山田", offset=offset)
        mock_get.assert_not_called()

    async def test_secret_is_masked_and_not_in_errors(self) -> None:
        secret = "do-not-leak-this-secret"
        settings = Settings(app_id=SecretStr(secret), request_delay=0, max_retries=1)
        assert secret not in repr(settings)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError(
                "upstream body with details", request=httpx.Request("GET", "https://example.test")
            )
            with pytest.raises(KakenError) as exc_info:
                await KakenClient(settings).search_projects(keyword="AI")
        assert secret not in str(exc_info.value)
        assert "upstream body" not in str(exc_info.value)

    @pytest.mark.parametrize(
        ("body", "content_type", "message"),
        [
            ("<html>error</html>", "text/html", "unexpected content type"),
            ("not XML", "application/xml", "invalid XML"),
        ],
    )
    async def test_rejects_invalid_project_response(
        self, settings: Settings, body: str, content_type: str, message: str
    ) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(body, content_type)
            with pytest.raises(KakenError, match=message):
                await KakenClient(settings).search_projects(keyword="AI")

    async def test_rejects_invalid_researcher_json(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response("not JSON", "application/json")
            with pytest.raises(KakenError, match="invalid JSON"):
                await KakenClient(settings).search_researchers(name="山田")

    async def test_rejects_xml_api_error_envelope(self, settings: Settings) -> None:
        body = "<error><code>403</code><reason>Forbidden</reason><detail>secret</detail></error>"
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(body, "application/xml")
            with pytest.raises(KakenError, match="KAKEN API error 403: Forbidden") as exc_info:
                await KakenClient(settings).search_projects(keyword="AI")
        assert "secret" not in str(exc_info.value)

    async def test_retries_rate_limit_response(self, settings: Settings) -> None:
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                response("rate limited", "text/plain", status=429),
                response(PROJECT_XML, "application/xml"),
            ]
            result = await KakenClient(settings).search_projects(keyword="AI")
        assert mock_get.await_count == 2
        assert result["total_count"] == 9898

    async def test_retries_nii_403_rate_limit_envelope(self, settings: Settings) -> None:
        rate_error = (
            "<error><code>403</code><reason>Forbidden</reason>"
            "<detail>Exceeds allowed rate</detail></error>"
        )
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                response(rate_error, "application/xml", status=403),
                response(PROJECT_XML, "application/xml"),
            ]
            result = await KakenClient(settings).search_projects(keyword="AI")
        assert mock_get.await_count == 2
        assert result["total_count"] == 9898

    async def test_serializes_concurrent_requests(self) -> None:
        settings = Settings(app_id=SecretStr("x"), request_delay=0.1, retry_delay=0)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response(PROJECT_XML, "application/xml")
            async with KakenClient(settings) as client:
                start = time.monotonic()
                await asyncio.gather(
                    client.search_projects(keyword="A"),
                    client.search_projects(keyword="B"),
                    client.search_projects(keyword="C"),
                )
                elapsed = time.monotonic() - start
        assert elapsed >= 0.2

    async def test_close_allows_http_client_recreation(self, settings: Settings) -> None:
        client = KakenClient(settings)
        first = client._http_client()
        await client.close()
        second = client._http_client()
        try:
            assert first.is_closed
            assert second is not first
            assert not second.is_closed
        finally:
            await client.close()
