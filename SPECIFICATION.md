# KAKEN MCP 仕様書

## 概要

科学研究費助成事業データベース（KAKEN）からデータを検索・取得するためのMCP（Model Context Protocol）サーバー。

**特徴:**
- API登録不要 - KAKENウェブサイトから直接データを取得（ウェブスクレイピング方式）
- 研究課題・研究者の検索が可能
- ページネーション対応

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

## データ取得方式

### ウェブスクレイピング

本MCPはKAKENウェブサイトのHTMLを直接パースしてデータを取得します。API登録（APP_ID）は不要です。

### 対象URL

| 機能 | URL形式 |
|-----|---------|
| 研究課題検索 | `https://kaken.nii.ac.jp/ja/search/?kw={keyword}` |
| 研究課題詳細 | `https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-{id}/` |
| 研究者検索 | `https://nrid.nii.ac.jp/ja/search/?qm={query}` |

### 検索パラメータ

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `kw` | フリーワード検索 | `kw=人工知能` |
| `q1` | 研究課題名 | `q1=機械学習` |
| `q4` | 研究者名 | `q4=田中` |
| `q5` | 研究機関 | `q5=東京大学` |
| `q15` | 研究者番号 | `q15=60273570` |
| `rw` | 取得件数 | `rw=100` |
| `st` | 開始位置（1-indexed） | `st=101` |

---

## MCP実装仕様

### 技術スタック

| 項目 | 値 |
|-----|-----|
| 言語 | Python 3.11+ |
| パッケージマネージャ | uv |
| MCPフレームワーク | FastMCP (>=2.0.0) |
| HTTPクライアント | httpx (>=0.28.0) |
| HTMLパーサー | BeautifulSoup4 (>=4.12.0) + lxml (>=5.0.0) |
| 設定管理 | pydantic-settings (>=2.0.0) |

### ディレクトリ構成

```
kaken-mcp/
├── pyproject.toml
├── README.md
├── SPECIFICATION.md
├── LICENSE
├── kaken_mcp/
│   ├── __init__.py
│   ├── __main__.py          # エントリーポイント
│   ├── server.py             # MCPサーバー
│   ├── client.py             # KAKENウェブスクレイピングクライアント
│   ├── config.py             # 設定管理
│   └── tools/
│       ├── __init__.py
│       ├── projects.py       # 研究課題検索ツール
│       └── researchers.py    # 研究者検索ツール
└── tests/
    ├── __init__.py
    └── test_client.py
```

### 設定

環境変数は不要です。オプションで以下の設定が可能：

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `KAKEN_BASE_URL` | KAKENベースURL | `https://kaken.nii.ac.jp` |
| `KAKEN_RESEARCHER_BASE_URL` | 研究者検索ベースURL | `https://nrid.nii.ac.jp` |
| `KAKEN_DEFAULT_LIMIT` | デフォルト取得件数 | `20` |
| `KAKEN_MAX_LIMIT` | 最大取得件数 | `200` |
| `KAKEN_REQUEST_TIMEOUT` | リクエストタイムアウト（秒） | `30.0` |

---

## MCPツール一覧

### 1. search_projects - 研究課題検索

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
| `limit` | integer | 取得件数（デフォルト: 20、最大: 200） | - |
| `offset` | integer | 開始位置（デフォルト: 0） | - |

**出力:**

```json
{
  "total_count": 150,
  "projects": [
    {
      "id": "KAKENHI-PROJECT-19H00001",
      "title": "研究課題名",
      "principal_investigator": "代表研究者名",
      "institution": "所属機関",
      "fiscal_year_start": 2019,
      "fiscal_year_end": 2023,
      "total_budget": 10000000,
      "url": "https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-19H00001/"
    }
  ]
}
```

### 2. get_project_detail - 研究課題詳細取得

特定の研究課題の詳細情報を取得する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `project_id` | string | 研究課題番号（例: "19H00001" または "KAKENHI-PROJECT-19H00001"） | ✓ |

**出力:**

```json
{
  "id": "KAKENHI-PROJECT-19H00001",
  "title": "研究課題名",
  "research_category": "基盤研究(A)",
  "principal_investigator": "代表研究者名",
  "institution": "所属機関",
  "fiscal_year_start": 2019,
  "fiscal_year_end": 2023,
  "total_budget": 10000000,
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "summary": "研究概要...",
  "url": "https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-19H00001/"
}
```

### 3. search_researchers - 研究者検索

研究者を検索する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `name` | string | 研究者名 | - |
| `researcher_number` | string | 研究者番号 | - |
| `institution` | string | 所属機関 | - |
| `research_field` | string | 研究分野 | - |
| `limit` | integer | 取得件数（デフォルト: 20、最大: 200） | - |
| `offset` | integer | 開始位置（デフォルト: 0） | - |

**出力:**

```json
{
  "total_count": 50,
  "researchers": [
    {
      "researcher_number": "1000000000001",
      "name": "研究者名",
      "affiliation": "東京大学 情報理工学系研究科",
      "url": "https://nrid.nii.ac.jp/ja/nrid/1000000000001/"
    }
  ]
}
```

### 4. get_researcher_projects - 研究者の研究課題一覧

特定の研究者が関わる研究課題一覧を取得する。

**入力パラメータ:**

| パラメータ | 型 | 説明 | 必須 |
|-----------|-----|------|------|
| `researcher_number` | string | 研究者番号 | ✓ |
| `role` | string | 役割フィルタ（"principal" または "co-investigator"） | - |
| `limit` | integer | 取得件数（デフォルト: 20、最大: 200） | - |
| `offset` | integer | 開始位置（デフォルト: 0） | - |

**出力:**

`search_projects` と同じ形式

---

## 使用例

### MCPサーバー起動

```bash
# uvでインストール
uv tool install git+https://github.com/leaveanest/kaken-mcp.git

# 実行（環境変数不要）
kaken-mcp
```

### Claude Desktop設定例

`claude_desktop_config.json` に以下を追加:

```json
{
  "mcpServers": {
    "kaken": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/leaveanest/kaken-mcp.git",
        "kaken-mcp"
      ]
    }
  }
}
```

### uvxで直接実行

```bash
uvx --from git+https://github.com/leaveanest/kaken-mcp.git kaken-mcp
```

---

## 注意事項

### 利用上の注意

- 短時間での大量アクセスは避けてください
- ウェブサイトの構造変更によりパースが失敗する可能性があります
- robots.txtで禁止されているパスへのアクセスは行いません

### 制限事項

- HTMLパースによるデータ取得のため、ウェブサイトの構造変更に影響を受ける可能性があります
- 一部のフィールドは取得できない場合があります

---

## 参考資料

- [KAKEN - 科学研究費助成事業データベース](https://kaken.nii.ac.jp/ja/)
- [KAKEN - 研究者をさがす](https://nrid.nii.ac.jp/ja/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [参考リポジトリ: alt-soracom-data-reader-mcp](https://github.com/leaveanest/alt-soracom-data-reader-mcp)

---

## 実装状況

- [x] 基本的なプロジェクト構造の作成
- [x] KAKENウェブスクレイピングクライアントの実装
- [x] 研究課題検索ツールの実装
- [x] 研究者検索ツールの実装
- [x] テストの作成
- [x] ドキュメントの整備
