# KAKEN MCP 仕様書

## 概要

科学研究費助成事業データベース（KAKEN）からデータを検索・取得するためのMCP（Model Context Protocol）サーバー。

## KAKENについて

### データベース概要

- **URL**: https://kaken.nii.ac.jp/ja/
- **運営**: 国立情報学研究所（NII）
- **内容**: 文部科学省および日本学術振興会が交付する科学研究費助成事業により行われた研究の情報
  - 採択課題（当初採択時のデータ）
  - 研究成果の概要
  - 研究成果報告書
  - 自己評価報告書

### 関連サービス

| サービス | URL | 説明 |
|---------|-----|------|
| KAKEN - 研究課題をさがす | https://kaken.nii.ac.jp/ja/ | 研究課題の検索 |
| KAKEN - 研究者をさがす | https://nrid.nii.ac.jp/ja/ | 研究者情報の検索 |
| GRANTS | https://grants.jst.go.jp/ | 複数データベース統合検索 |

---

## KAKEN API 仕様

### 認証

APIを利用するには、CiNii Web API開発者登録で取得したApplication IDが必要。

- **登録URL**: https://support.nii.ac.jp/ja/cinii/api/developer
- **パラメータ形式**: `appid=xxxxxxxx`

### 研究課題検索 API

#### エンドポイント

```
https://kaken.nii.ac.jp/opensearch/?(parameter=value)&(parameter=value)&...
```

#### 主要パラメータ（推定）

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `appid` | アプリケーションID（必須） | `appid=xxxxxxxx` |
| `format` | 出力形式（デフォルト: html5） | `format=xml`, `format=json` |
| `q` | フリーワード検索 | `q=人工知能` |
| `q1` | 研究課題名 | `q1=機械学習` |
| `q15` | 研究者番号 | `q15=60273570` |
| `rw` | 取得件数 | `rw=100` |
| `st` | 開始位置（ページネーション） | `st=101` |

#### 詳細パラメータドキュメント

- https://bitbucket.org/niijp/kaken_definition/src/master/KAKEN_API_parameters_document_Ja.pdf

### 研究者検索 API

#### エンドポイント

```
https://nrid.nii.ac.jp/opensearch/?(parameter=value)&(parameter=value)&...
```

#### 主要パラメータ

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `appid` | アプリケーションID（必須） | `appid=xxxxxxxx` |
| `format` | 出力形式 | `format=json` |
| `qm` | 検索クエリ（ワイルドカード対応） | `qm=田中*` |
| `rw` | 取得件数 | `rw=500` |
| `st` | 開始位置 | `st=1` |

### レスポンス形式

#### XML形式（OpenSearch標準）

```xml
<feed>
  <totalResults>100</totalResults>
  <startIndex>1</startIndex>
  <itemsPerPage>20</itemsPerPage>
  <entry>
    <title>研究課題名</title>
    <link href="https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-XXXXXXXX/"/>
    <!-- その他の情報 -->
  </entry>
</feed>
```

#### JSON形式

```json
{
  "totalResults": 100,
  "startIndex": 1,
  "itemsPerPage": 20,
  "researchers": [
    {
      "name": "研究者名",
      "affiliation": "所属機関"
    }
  ]
}
```

### RDFデータ

研究課題の詳細情報はRDF形式でも取得可能:

```
https://kaken.nii.ac.jp/rdf/p/{課題番号}
```

---

## MCP実装仕様

### 技術スタック

参考リポジトリ（alt-soracom-data-reader-mcp）に基づく:

| 項目 | 値 |
|-----|-----|
| 言語 | Python 3.11+ |
| パッケージマネージャ | uv |
| MCPフレームワーク | FastMCP (>=2.13.3) |
| HTTP クライアント | httpx (>=0.28.0) |
| 設定管理 | pydantic-settings (>=2.12.0) |

### ディレクトリ構成

```
kaken-mcp/
├── pyproject.toml
├── README.md
├── kaken_mcp/
│   ├── __init__.py
│   ├── __main__.py          # エントリーポイント
│   ├── server.py             # MCPサーバー
│   ├── client.py             # KAKEN APIクライアント
│   ├── config.py             # 設定管理
│   └── tools/
│       ├── __init__.py
│       ├── projects.py       # 研究課題検索ツール
│       └── researchers.py    # 研究者検索ツール
└── tests/
    └── ...
```

### 環境変数

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `KAKEN_APP_ID` | CiNii APIのApplication ID | ✓ |

### MCPツール一覧

#### 1. search_projects - 研究課題検索

研究課題をキーワードや条件で検索する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `keyword` | string | フリーワード検索 | - |
| `title` | string | 研究課題名 | - |
| `researcher_name` | string | 研究者名 | - |
| `researcher_number` | string | 研究者番号 | - |
| `institution` | string | 研究機関名 | - |
| `research_field` | string | 研究分野 | - |
| `fiscal_year_from` | integer | 研究期間（開始年度） | - |
| `fiscal_year_to` | integer | 研究期間（終了年度） | - |
| `limit` | integer | 取得件数（デフォルト: 20） | - |
| `offset` | integer | 開始位置（デフォルト: 0） | - |

**出力:**

```json
{
  "total_count": 150,
  "projects": [
    {
      "id": "KAKENHI-PROJECT-XXXXXXXX",
      "title": "研究課題名",
      "principal_investigator": "代表研究者名",
      "institution": "所属機関",
      "research_field": "研究分野",
      "fiscal_year": "2020-2024",
      "total_budget": 10000000,
      "url": "https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-XXXXXXXX/"
    }
  ]
}
```

#### 2. get_project_detail - 研究課題詳細取得

特定の研究課題の詳細情報を取得する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `project_id` | string | 研究課題番号 | ✓ |

**出力:**

```json
{
  "id": "KAKENHI-PROJECT-XXXXXXXX",
  "title": "研究課題名",
  "title_en": "Research Project Title",
  "principal_investigator": {
    "name": "代表研究者名",
    "name_en": "Principal Investigator Name",
    "researcher_number": "60273570",
    "institution": "所属機関"
  },
  "co_investigators": [...],
  "research_field": "研究分野",
  "keywords": ["キーワード1", "キーワード2"],
  "abstract": "研究概要...",
  "fiscal_years": {
    "start": 2020,
    "end": 2024
  },
  "budget": {
    "total": 10000000,
    "by_year": {...}
  },
  "publications": [...],
  "url": "https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-XXXXXXXX/"
}
```

#### 3. search_researchers - 研究者検索

研究者を検索する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `name` | string | 研究者名 | - |
| `researcher_number` | string | 研究者番号 | - |
| `institution` | string | 所属機関 | - |
| `research_field` | string | 研究分野 | - |
| `limit` | integer | 取得件数（デフォルト: 20） | - |
| `offset` | integer | 開始位置（デフォルト: 0） | - |

**出力:**

```json
{
  "total_count": 50,
  "researchers": [
    {
      "researcher_number": "60273570",
      "name": "研究者名",
      "name_en": "Researcher Name",
      "institution": "所属機関",
      "department": "所属部局",
      "position": "職名",
      "research_fields": ["研究分野1", "研究分野2"],
      "url": "https://nrid.nii.ac.jp/ja/nrid/XXXXXXXX/"
    }
  ]
}
```

#### 4. get_researcher_projects - 研究者の研究課題一覧

特定の研究者が関わる研究課題一覧を取得する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `researcher_number` | string | 研究者番号 | ✓ |
| `role` | string | 役割（代表者/分担者） | - |
| `limit` | integer | 取得件数 | - |
| `offset` | integer | 開始位置 | - |

---

## 使用例

### MCPサーバー起動

```bash
# uvでインストール
uv tool install git+https://github.com/leaveanest/kaken-mcp.git

# 実行
KAKEN_APP_ID=your_app_id kaken-mcp
```

### Claude Desktop設定例

```json
{
  "mcpServers": {
    "kaken": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/leaveanest/kaken-mcp.git",
        "kaken-mcp"
      ],
      "env": {
        "KAKEN_APP_ID": "your_application_id"
      }
    }
  }
}
```

---

## 注意事項

### API利用規約

- 短時間での大量アクセスは禁止
- 規定に従わないアクセスは予告なくブロックされる可能性あり
- robots.txtで禁止されているパスへのアクセスは不可

### 参考資料

- [KAKEN API ドキュメント](https://support.nii.ac.jp/en/kaken/api/api_outline)
- [CiNii API開発者登録](https://support.nii.ac.jp/ja/cinii/api/developer)
- [パラメータ定義PDF](https://bitbucket.org/niijp/kaken_definition/src/master/KAKEN_API_parameters_document_Ja.pdf)
- [参考リポジトリ: alt-soracom-data-reader-mcp](https://github.com/leaveanest/alt-soracom-data-reader-mcp)

---

## 今後の実装予定

1. [ ] 基本的なプロジェクト構造の作成
2. [ ] KAKEN APIクライアントの実装
3. [ ] 研究課題検索ツールの実装
4. [ ] 研究者検索ツールの実装
5. [ ] テストの作成
6. [ ] ドキュメントの整備
