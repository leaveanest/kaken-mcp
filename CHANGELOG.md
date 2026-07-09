# Changelog

このプロジェクトの主な変更を記録します。形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に、バージョニングは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

## [Unreleased]

### Fixed
- 検索 URL パラメータを現行 KAKEN サイトのものに更新（`q1`→`qa` 等）。旧パラメータはサイト側で黙って無視されており、`title` などのフィルタが機能していなかった（[#2](https://github.com/leaveanest/kaken-mcp/pull/2) by @anabanted）
- レート制限が実際には機能していなかった問題を修正。ツール呼び出し毎に `KakenClient` を生成していたためタイマーが毎回リセットされ、並行呼び出しでは同時リクエストになっていた。全ツールで単一クライアントを共有し、ロックでリクエスト開始間隔を直列化（接続プールも再利用されるように）
- `get_project_detail` の project_id を検証し、パス・クエリを注入できる入力（`../` や `?` を含む ID）を拒否
- サーバー instructions から、存在しない `KAKEN_APP_ID` 設定を要求する誤った記載を削除
- `KakenClient` が環境変数のプロキシ設定を拾わないように変更（`trust_env=False`）

### Changed
- 起動オーバーヘッドを削減（lxml 依存を外し、標準ライブラリの `html.parser` へ変更）

### Added
- CI（GitHub Actions: ruff / mypy / pytest、Python 3.11〜3.13）
- CONTRIBUTING.md / Issue・PR テンプレート / SECURITY.md / この CHANGELOG
- `py.typed`（型情報をパッケージに同梱）

## [0.1.0] - 2025-12-24

### Added
- 初期実装
- MCP ツール 4 種: `search_projects` / `get_project_detail` / `search_researchers` / `get_researcher_projects`
- KAKEN ウェブサイトのスクレイピングによるデータ取得（API キー・登録不要）
- レート制限（リクエスト間 1 秒）と指数バックオフ付きリトライ
