# 第5回 提出案内

公開リポジトリ：<https://github.com/masahikoyr/lecture-ai-engineering-2026>

**実装・自動テスト37件・Codespacesでの実API比較6件と、その結果の整理を完了。**

## 提出内容

- [answer.md](answer.md)：実装、比較条件、回答・引用・時間・トークン・費用、効果と限界。
- [live_result.json](live_result.json)：利用者から受領した実測ファイル。内容を変更せず保存。
- [live_review.json](live_review.json)：元ファイルとは分けたAI支援による本文照合と判定。独立した人手評価ではない。
- [offline_result.json](offline_result.json)：APIを使わない固定ヒットの取得処理検証。実API比較とは別の証拠。

元の`live_result.json`内の`manual_review`は未記入のまま保持し、照合結果は`live_review.json`とレポートで示す。今回の6件の回答が期待を満たしたことを、一般的な正答率と混同しない。

## Quri入力用

### Q1

実装｜Implementation

### Q2

https://github.com/masahikoyr/lecture-ai-engineering-2026

### Q3（300文字以内）

検索したページの前後1ページを、同じ資料内で重複なく取得するよう改良しました。工夫した点は、通常版とツール名・説明・指示文をそろえ、取得処理の違いを比較しやすくしたことです。3問×2方式を実APIで比較し、自動テスト37件も確認しました。メモリの質問では検索が2回から1回となり、入力トークン数が約27.5％減りました。一方、LoRAや答えのない質問では入力と費用が増えました。必要な根拠は通常版にも含まれていたため、追加ページの効果を断定せず、回答・引用根拠・負担を分けて考察した点を評価いただきたいです。

## 再現する場合

提出用の比較は完了しているため、再実行は不要。追試する場合は、既存の実測ファイルを保ったまま別の出力先を指定する。

```bash
uv sync --frozen
uv run pytest -q
uv run python -m scripts.compare_lec05 --output lectures/05/live_result_recheck.json
```

第5回の配布コードと検索DBは`lec05`に取り込み済み。APIキーは従来のCodespaces secretを使用する。モデルを切り替えた結果を元の条件のペアと混ぜない。

自分のfork内の`lec05`→`main`のPRを確認し、Quriに上記を入力する。Quriへの送信とPRのマージはまだ行っていない。作業終了後はCodespacesを停止する。
