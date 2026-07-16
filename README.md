# KAKEN MCP

[![CI](https://github.com/leaveanest/kaken-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/leaveanest/kaken-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

科学研究費助成事業データベース（KAKEN）にアクセスするためのMCP（Model Context Protocol）サーバー。

## 概要

KAKEN MCPは、日本の科学研究費助成事業（KAKENHI）データベースから研究課題や研究者の情報を検索・取得するためのMCPサーバーです。LLM（Claude等）から直接KAKENデータベースにアクセスし、研究情報の調査や分析を行うことができます。

**特徴:**
- KAKEN公式OpenSearch API（研究課題XML・研究者JSON）からデータを取得
- HTMLスクレイピングに非依存
- 研究課題・研究者の検索が可能
- ページネーション対応

## 機能

- **研究課題検索** (`search_projects`): キーワード、研究者名、機関名などで研究課題を検索
- **研究課題詳細取得** (`get_project_detail`): 特定の研究課題の詳細情報を取得
- **研究者検索** (`search_researchers`): 研究者名、所属機関などで研究者を検索
- **研究者の課題一覧** (`get_researcher_projects`): 特定の研究者が関わる研究課題を取得

## 必要条件

- Python 3.11以上
- [CiNiiウェブAPI利用登録](https://support.nii.ac.jp/ja/cinii/api/developer)で発行されたアプリケーションID

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

### アプリケーションIDの設定

KAKEN APIではCiNiiウェブAPI利用登録で発行されたアプリケーションIDが必要です。シェルで次の環境変数を設定してください。

```bash
export KAKEN_APP_ID="発行されたアプリケーションID"
```

値はリポジトリへ記録せず、利用環境の秘密管理機能、またはアクセス権を制限したMCP設定で管理してください。

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

### Codex での設定

`~/.codex/config.toml` に以下を追加:

```toml
[mcp_servers.kaken]
command = "uvx"
args = ["--from", "git+https://github.com/leaveanest/kaken-mcp.git", "kaken-mcp"]
env = { KAKEN_APP_ID = "発行されたアプリケーションID" }
startup_timeout_sec = 30
tool_timeout_sec = 120
enabled = true
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

## コントリビュート

バグ報告・機能要望・PR を歓迎します。始め方は [CONTRIBUTING.md](CONTRIBUTING.md) を見てください。

## ライセンス

MIT License

## 参考資料

- [KAKEN - 科学研究費助成事業データベース](https://kaken.nii.ac.jp/ja/)
- [KAKEN APIドキュメント](https://support.nii.ac.jp/ja/kaken/api/api_outline)
- [KAKEN公開XML定義・APIパラメータ](https://bitbucket.org/niijp/kaken_definition/src/master/)
- [CiNiiウェブAPI利用登録](https://support.nii.ac.jp/ja/cinii/api/developer)
- [Model Context Protocol](https://modelcontextprotocol.io/)
