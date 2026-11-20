# 第5回 実装課題の実行・提出手順

公開リポジトリ：<https://github.com/masahikoyr/lecture-ai-engineering-2026>

**実装と自動テストは完了。提出を仕上げるには、Codespacesで実API比較を実行し、回答と引用根拠を確認する。現時点では比較完了とは申告しない。**

## 1. Codespacesでlec05を開く

まず未コミットの変更を確認する。

```bash
git status --short
```

変更が表示された場合は、そのブランチで保存・commitしてから切り替える。変更を捨てる必要はない。

```bash
git fetch origin
git switch lec05
uv sync --frozen
uv run pytest -q
```

第5回の配布コードと検索DBは取り込み済み。`main`の更新や索引の再作成は不要。

## 2. 実APIで3問×2方式を比較する

以前登録したCodespaces secret `GEMINI_API_KEY`をそのまま使う。キーをチャットやコードへ貼る必要はない。

```bash
uv run python -m scripts.compare_lec05
```

6組の回答、取得ページ、時間、入出力トークン、応答回数、生成API推定費用を`lectures/05/live_result.json`へ保存する。回答の正しさは自動採点しない。

429/503などで止まったらAPIの案内に従って待ち、次で再開する。成功済みの組は繰り返さず、失敗した試行も残す。

```bash
uv run python -m scripts.compare_lec05 --resume
```

既存ファイルへの新規実行は上書きせず停止する。同じ条件なら`--resume`を使う。モデルを変える場合は別ファイルへ新規実行する。

```bash
AIE_MODEL=gemini-3.1-flash-lite uv run python -m scripts.compare_lec05 --output lectures/05/live_result_flash31.json
```

元の結果と別モデルの結果を一つのペアに混ぜない。再開時も同じモデル指定を付ける。

## 3. 結果を確認してレポートを仕上げる

結果JSONの回答を読み、[comparison_cases.json](comparison_cases.json)の期待するふるまいと資料本文を照合する。

- LoRA：重みの固定、A・Bの学習、QLoRAの4bit化を説明したか。
- メモリ：同一セッションの要約と外部保存を区別し、日々のメモが全部長期メモリになると誤解していないか。
- 実測ログのない質問：時間や正答率を作らず、確認できないと答えたか。
- 前後追加：役立った根拠と不要な情報、入力の負担はどう変わったか。

`manual_review`と[answer.md](answer.md)の実API比較表・考察に確認結果を追記する。JSONをこのチャットに添付すれば、結果の整理とレポートへの反映を続けられる。

Codespaces側で保存する場合は、対象ファイルだけをcommitする。

```bash
git add lectures/05/live_result.json lectures/05/answer.md
git commit -m "第5回 実API比較の結果を記録"
git push origin lec05
```

別モデルの結果を使った場合はファイル名を置き換える。

## 4. 提出

比較とレポートが完成したら、自分のfork内の`lec05`→`main`のPRを使用する。

- Q1：実装｜Implementation（実測と確認を終えた後）
- Q2：<https://github.com/masahikoyr/lecture-ai-engineering-2026>
- Q3：実際に観察した改善・失敗・負担を記載する。文字数はQuriの表示に従う。

作業終了後はCodespacesを停止する。
