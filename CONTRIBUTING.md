# コントリビューションガイド

kaken-mcp への貢献に興味を持っていただきありがとうございます。バグ報告、機能提案、プルリクエスト、いずれも歓迎します。

## 開発環境のセットアップ

[uv](https://docs.astral.sh/uv/) を使います。

```bash
git clone https://github.com/leaveanest/kaken-mcp.git
cd kaken-mcp
uv sync --dev
```

## 開発の流れ

1. 大きな変更の場合は、先に Issue で相談してください
2. ブランチを切る（`fix/...` / `feature/...`）
3. 変更を加え、対応するテストを追加する
4. ローカルチェックを通す（下記）
5. PR を出す

## ローカルチェック

PR を出す前に以下がすべて通ることを確認してください。CI でも同じものが走ります。

```bash
uv run ruff check .
uv run mypy kaken_mcp
uv run pytest
```

## KAKEN APIに関わる変更の注意

このプロジェクトは kaken.nii.ac.jp / nrid.nii.ac.jp の公式OpenSearch APIを利用します。検索パラメータやXML・JSON変換に関わる変更では、次の点をお願いします。

- **公式定義を確認する**: [KAKEN公開XML定義・APIパラメータ](https://bitbucket.org/niijp/kaken_definition/src/master/)と実レスポンスの両方に照らして変更してください
- **登録済みappidで限定検証する**: `KAKEN_APP_ID` を環境変数から渡し、フィルタ変更時は期待した条件と総件数を確認してください。appidをログ、fixture、PR本文へ記録しないでください
- **レート制限を守る**: 検証時はリクエスト間に 1 秒以上の間隔を置き、識別可能な User-Agent を付けてください
- PRにはappidを除いた検索条件と確認結果を書いてください

## バグ報告

Issue テンプレートに沿って、再現手順と期待する挙動を書いてください。検索系のバグは、検索条件と実際に返ってきた件数があると調査が早くなります。
