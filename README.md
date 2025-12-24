# KAKEN MCP

科学研究費助成事業データベース（KAKEN）にアクセスするためのMCP（Model Context Protocol）サーバー。

## 概要

KAKEN MCPは、日本の科学研究費助成事業（KAKENHI）データベースから研究課題や研究者の情報を検索・取得するためのMCPサーバーです。LLM（Claude等）から直接KAKENデータベースにアクセスし、研究情報の調査や分析を行うことができます。

## 機能

- **研究課題検索** (`search_projects`): キーワード、研究者名、機関名などで研究課題を検索
- **研究課題詳細取得** (`get_project_detail`): 特定の研究課題の詳細情報を取得
- **研究者検索** (`search_researchers`): 研究者名、所属機関などで研究者を検索
- **研究者の課題一覧** (`get_researcher_projects`): 特定の研究者が関わる研究課題を取得

## 必要条件

- Python 3.11以上
- CiNii API Application ID（[開発者登録](https://support.nii.ac.jp/ja/cinii/api/developer)で取得）

## インストール

### uvを使用する場合

```bash
# GitHubから直接インストール
uv tool install git+https://github.com/leaveanest/kaken-mcp.git

# または、uvxで直接実行
uvx --from git+https://github.com/leaveanest/kaken-mcp.git kaken-mcp
```

### pipを使用する場合

```bash
pip install git+https://github.com/leaveanest/kaken-mcp.git
```

## 使用方法

### 環境変数の設定

```bash
export KAKEN_APP_ID="your_application_id"
```

### MCPサーバーの起動

```bash
kaken-mcp
```

### Claude Desktop での設定

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
      ],
      "env": {
        "KAKEN_APP_ID": "your_application_id"
      }
    }
  }
}
```

## ツール詳細

### search_projects

研究課題を検索します。

**パラメータ:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `keyword` | string | フリーワード検索 |
| `title` | string | 研究課題名 |
| `researcher_name` | string | 研究者名 |
| `researcher_number` | string | 研究者番号 |
| `institution` | string | 研究機関名 |
| `research_field` | string | 研究分野 |
| `fiscal_year_from` | integer | 研究期間（開始年度） |
| `fiscal_year_to` | integer | 研究期間（終了年度） |
| `limit` | integer | 取得件数（デフォルト: 20） |
| `offset` | integer | 開始位置（デフォルト: 0） |

### get_project_detail

特定の研究課題の詳細情報を取得します。

**パラメータ:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `project_id` | string | 研究課題番号（必須） |

### search_researchers

研究者を検索します。

**パラメータ:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `name` | string | 研究者名 |
| `researcher_number` | string | 研究者番号 |
| `institution` | string | 所属機関 |
| `research_field` | string | 研究分野 |
| `limit` | integer | 取得件数（デフォルト: 20） |
| `offset` | integer | 開始位置（デフォルト: 0） |

### get_researcher_projects

特定の研究者の研究課題一覧を取得します。

**パラメータ:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `researcher_number` | string | 研究者番号（必須） |
| `role` | string | 役割（"principal" or "co-investigator"） |
| `limit` | integer | 取得件数（デフォルト: 20） |
| `offset` | integer | 開始位置（デフォルト: 0） |

## 開発

### セットアップ

```bash
git clone https://github.com/leaveanest/kaken-mcp.git
cd kaken-mcp
uv sync --dev
```

### テストの実行

```bash
uv run pytest
```

### 型チェック

```bash
uv run mypy kaken_mcp
```

### リント

```bash
uv run ruff check kaken_mcp
```

## ライセンス

MIT License

## 参考資料

- [KAKEN - 科学研究費助成事業データベース](https://kaken.nii.ac.jp/ja/)
- [KAKEN API ドキュメント](https://support.nii.ac.jp/en/kaken/api/api_outline)
- [CiNii API開発者登録](https://support.nii.ac.jp/ja/cinii/api/developer)
- [Model Context Protocol](https://modelcontextprotocol.io/)
