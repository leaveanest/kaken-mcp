# KAKEN MCP 仕様書

## 概要

科学研究費助成事業データベース（KAKEN）からデータを検索・取得するためのMCP（Model Context Protocol）サーバー。

**特徴:**
- KAKEN公式OpenSearch APIから取得（HTMLスクレイピング非依存）
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

### KAKEN OpenSearch API

本MCPはKAKEN公式OpenSearch APIを使用します。研究課題はXML、研究者はJSONで取得し、既存MCPツールの返却形式へ正規化します。利用にはCiNiiウェブAPI利用登録で発行されたアプリケーションIDが必要です。

### 対象URL

| 機能 | URL形式 |
|-----|---------|
| 研究課題検索 | `https://kaken.nii.ac.jp/opensearch/?format=xml&appid=...` |
| 研究課題詳細 | 研究課題APIを `qb={project_id}` で検索 |
| 研究者検索 | `https://nrid.nii.ac.jp/opensearch/?format=json&appid=...` |

### 検索パラメータ

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `kw` | フリーワード検索 | `kw=人工知能` |
| `qa` | 研究課題名 | `qa=機械学習` |
| `qg` | 研究者名 | `qg=田中` |
| `qe` | 研究機関 | `qe=東京大学` |
| `qd` | 審査区分・研究分野 | `qd=情報学` |
| `s1` | 研究期間の開始年度 | `s1=2020` |
| `s2` | 研究期間の終了年度 | `s2=2023` |
| `qm` | 研究者番号 | `qm=60273570` |
| `c2` | 役割（研究代表者/分担者） | `c2=principal_investigator` |
| `rw` | 取得件数 | `rw=100` |
| `st` | 開始位置（1-indexed） | `st=101` |

`limit` は既存MCP契約上1～200を受け付けます。APIの `rw` は20・50・100・200・500の列挙値であるため、内部では要求件数以上の最小値へ切り上げ、返却時に要求件数へ絞ります。`offset` はMCP側の0-basedからAPIの `st`（1-based）へ変換します。

---

## MCP実装仕様

### 技術スタック

| 項目 | 値 |
|-----|-----|
| 言語 | Python 3.11+ |
| パッケージマネージャ | uv |
| MCPフレームワーク | FastMCP (>=2.0.0) |
| HTTPクライアント | httpx (>=0.28.0) |
| XMLパーサー | Python標準ライブラリ `xml.etree.ElementTree` |
| JSONパーサー | Python標準ライブラリ `json` |
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
│   ├── client.py             # KAKEN OpenSearch APIクライアント
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

以下の環境変数を使用します。

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `KAKEN_APP_ID` | CiNiiウェブAPI利用登録で発行されたアプリケーションID（API呼び出し時に必須） | なし |
| `KAKEN_BASE_URL` | 返却する研究課題リンクのベースURL | `https://kaken.nii.ac.jp` |
| `KAKEN_RESEARCHER_BASE_URL` | 返却する研究者リンクのベースURL | `https://nrid.nii.ac.jp` |
| `KAKEN_PROJECT_API_URL` | 研究課題OpenSearch API URL | `https://kaken.nii.ac.jp/opensearch/` |
| `KAKEN_RESEARCHER_API_URL` | 研究者OpenSearch API URL | `https://nrid.nii.ac.jp/opensearch/` |
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
      "researcher_number": "12345678",
      "name": "研究者名",
      "affiliation": "東京大学 情報理工学系研究科",
      "url": "https://nrid.nii.ac.jp/ja/nrid/1000012345678/"
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

# appidを設定して実行
export KAKEN_APP_ID="発行されたアプリケーションID"
kaken-mcp
```

### Claude Desktop設定例

`claude_desktop_config.json` に以下を追加:

```json
{
  "mcpServers": {
    "kaken": {
      "command": "uvx",
      "env": {
        "KAKEN_APP_ID": "発行されたアプリケーションID"
      },
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
- `KAKEN_APP_ID` をログ、リポジトリ、Issue、PRへ記録しないでください
- 公式API定義の更新時はXML・JSON変換の追随が必要です

### 制限事項

- KAKEN APIの仕様・レート制限・最大開始位置の制約を受けます
- 一部のフィールドは取得できない場合があります

---

## 参考資料

- [KAKEN - 科学研究費助成事業データベース](https://kaken.nii.ac.jp/ja/)
- [KAKEN - 研究者をさがす](https://nrid.nii.ac.jp/ja/)
- [KAKEN APIドキュメント](https://support.nii.ac.jp/ja/kaken/api/api_outline)
- [KAKEN公開XML定義・APIパラメータ](https://bitbucket.org/niijp/kaken_definition/src/master/)
- [CiNiiウェブAPI利用登録](https://support.nii.ac.jp/ja/cinii/api/developer)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [参考リポジトリ: alt-soracom-data-reader-mcp](https://github.com/leaveanest/alt-soracom-data-reader-mcp)

---

## 実装状況

- [x] 基本的なプロジェクト構造の作成
- [x] KAKEN OpenSearch APIクライアントの実装
- [x] 研究課題検索ツールの実装
- [x] 研究者検索ツールの実装
- [x] テストの作成
- [x] ドキュメントの整備
