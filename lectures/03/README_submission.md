# 第3回 実装課題：動作確認と提出

公開リポジトリ：https://github.com/masahikoyr/lecture-ai-engineering-2026
ブランチ：lec03。PRの宛先は自分のforkのmain。

## 現在の状態

実装、APIなしの再現検証、解答作成が完了。自動テスト34件合格。
本人のCodespacesでGemini実APIによる承認・拒否を実行し、結果をanswer.mdへ反映済み。承認後の503発生後もJSON1件の保存を確認し、拒否ケースではdeniedと最終回答を確認した。拒否後のファイル件数のみ、補助コマンドのSyntaxErrorにより未確認。
GPU・Colabは不要。第1回で用意したCodespacesとGEMINI_API_KEYを利用できる。
キーをチャットやコードに貼る必要はない。

## 1. Codespacesでブランチを開く

既存のCodespacesを開き、ターミナルで `git status --short` を確認する。
未コミットの作業がある場合は上書きせず、先に保存する。
変更のない状態で、次を順番に実行する。

```bash
git fetch origin
git switch lec03
uv sync --frozen
uv run pytest -q
uv run python -m app.agent --list-tools
```

依存関係は講座の固定版をそのまま使う。mainを更新したり、前の宿題をマージしたりする必要はない。
すでにlec03を開いている場合は、作業を保存後に `git pull --ff-only origin lec03` で更新する。

## 2. Geminiで用語集と確認問題を確認

```bash
uv run python -m app.agent --trace "AIE2026の講座で使うlecNN-startタグとは何ですか？"
uv run python -m app.agent --trace "第2回の内容から確認問題を1問出してください"
```

`search_glossary`や`make_quiz`が呼ばれたか、引数、回答、requestsを確認する。
質問文が変わるとモデルが選ぶツールも変わるため、実際のtraceを記録する。
第1回の単発モードとの比較も行う場合：

```bash
uv run python -m app.ask "AIE2026の講座で使うlecNN-startタグとは何ですか？"
```

## 3. 保存の承認・拒否を確認

以下を実行する。

```bash
uv run python -m app.agent --trace "LoRAについて、基盤モデルを固定して追加行列を学習すると学びました。学習テーマをLoRA、学んだ内容をこの文章として学習記録を保存してください。"
```

保存内容が表示されて `[y/N]` を聞かれたら、内容を読んで `y` を入力する。
traceに `save_learning_log` の呼出しと `saved: true` が表示され、learning_log/にJSONが1件増えることを確認する。

同じコマンドをもう一度実行し、今度は `n` を入力する。
ファイル数が増えず、`The tool call was denied.` が返ることを確認する。
空のままEnter、EOF、Ctrl+Cも保存を拒否する。

保存ファイル数を確認するには、次を利用できる（内容は表示しない）。

```bash
python -c "from pathlib import Path; print(len(list(Path('learning_log').glob('*.json'))))"
```

モデルが保存ツールを呼ばず説明だけした場合は、実際の回答をそのまま記録して相談する。
429なら時間を置いて再実行する。承認後に503が出た場合は、保存だけは完了していることがある。件数と内容を確認し、同じ保存を無条件に再実行しない。
キー未設定の場合はCodespaces secretのRepository accessを確認し、Codespacesを再起動する。
保存前後の比較は、既存ログがある場合は0/1でなく「何件増えたか」で確認する。

## 4. 結果を解答へ追記

lectures/03/answer.mdの「Geminiでの最終確認」へ、実行日、起動時のmodel名、実際のツール名と引数、requests、承認後・拒否後のファイル件数を記載する。
承認画面とtraceのテキストをこのチャットに共有してもよい。キーや個人情報は含めない。

個人のlearning_log/配下のファイルは公開しない。
モデルの動作確認の記録は、架空・学習用の内容のみを抜粋してanswer.mdへ記載する。
`offline_trace.txt`は模擬モデルの実行記録なので、実APIの結果で上書きせず区別する。

```bash
git diff --check
git add lectures/03/answer.md
git commit -m "第3回: Geminiでの承認付き保存の実行結果を追記"
git push origin lec03
```

同じPRへ反映される。確認後にDraft PRをReady for reviewへ変更する。
提出フォームのレベルは「実装」、URLは以下を使用する。

https://github.com/masahikoyr/lecture-ai-engineering-2026

備考欄があればPR URLも添える。mainへのマージは講座の指示がなければ不要。
使い終えたらCodespacesを停止する。

## APIなしの再現確認

```bash
uv run python -m scripts.verify_lec03
```

模擬モデルが決まったツールを選び、模擬入力y/n/空文字を渡す。
Pydantic AIの承認処理・停止・再開・JSON保存自体は実行するが、Geminiの性能は評価しない。
保存先は一時フォルダで、検証後に消去する。
実行記録はlectures/03/offline_result.jsonとoffline_trace.txtへ保存する。
