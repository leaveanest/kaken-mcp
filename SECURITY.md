# セキュリティポリシー

## 脆弱性の報告

セキュリティに関わる問題を見つけた場合は、公開 Issue ではなく [GitHub Security Advisories](https://github.com/leaveanest/kaken-mcp/security/advisories/new) から非公開で報告してください。

## サポート対象

main ブランチ（最新リリース）のみを対象とします。

## 補足

このツールは公開データベース（kaken.nii.ac.jp / nrid.nii.ac.jp）の公開情報のみを取得します。KAKEN APIの利用には `KAKEN_APP_ID` が必要です。

- appidは環境変数で渡し、リポジトリ、ログ、Issue、テストfixtureへ記録しないでください
- 通信エラーの利用者向けメッセージには、appidを含むリクエストURLを出力しません
- 誤ってappidを公開した場合は、CiNiiウェブAPIの管理画面で速やかに失効・再発行してください
