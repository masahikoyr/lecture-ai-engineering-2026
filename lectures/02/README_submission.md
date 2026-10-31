# 第2回：実行と提出の手順

公開リポジトリ：https://github.com/masahikoyr/lecture-ai-engineering-2026
作業ブランチ：lec02。PRは自分のforkのmainへ作成する。講座公式へは出さない。

## 現在の状態

2026年11月1日（日本時間）に、本人がColab Tesla T4で実行した結果を反映済み。
40ステップ・20エポックの学習が完了。形式遵守率は28.57%から100%、内容正解率は9.52%から90.48%となった。
学習前後42件の採点と集計の整合性を再確認し、解答に結果と限界を記載した。

解答：https://github.com/masahikoyr/lecture-ai-engineering-2026/blob/lec02/lectures/02/answer.md
PR：https://github.com/masahikoyr/lecture-ai-engineering-2026/pull/2

以下は再現実行と結果更新の手順。追加学習は提出のためには不要。
解答を本人が読み、内容を確認したうえで、提出フォームへ公開リポジトリURLを記載する。
本作業ではフォーム送信・mainへのマージは行わない。

## 1. Colabで開く

https://colab.research.google.com/github/masahikoyr/lecture-ai-engineering-2026/blob/lec02/notebooks/AIEngineering2026_Lec02_SOC_FAQ.ipynb

「ファイル → ドライブにコピーを保存」で自分のコピーを作る。
「ランタイム → ランタイムのタイプを変更 → T4 GPU」を選択する。
Gemini APIキーは不要。GPUでHugging Faceの公開モデルを学習する。
通常は新しい契約や有料環境の用意は不要。T4が割り当てられないときは、時間を変えて試す。

## 2. 上から実行

初回ダウンロードを含め、15〜30分程度を確保する。実際の時間は環境で変わる。
セクション0から7まで順番に実行する。「すべてのセルを実行」でもよい。
ライブラリとモデルのrevisionは講座と同じ固定版。独自に版を上げない。
各セルの実行が完了するまで待ち、エラーがあればそこで止めて原因を確認する。
同じセッションで学習セルを何度も繰り返さない。やり直すときはセッションを再起動して先頭から実行する。

原本の講座FAQによる演習も記録したい場合は、別のColabコピー・別セッションで講座公式ノートブックを実行する。
今回の独自ノートブックは、宿題の独自FAQによる前後比較を行う。

## 3. 結果を保存

最終セルで `AIEngineering2026_Lec02_results.zip` がダウンロードされる。
ブラウザの自動ダウンロードが動かなければ、Colab左のファイル一覧で `/content/AIEngineering2026_Lec02_results.zip` を右クリックし、ダウンロードする。
生成されるZIPには、以下が `lectures/02/` 配下に入る。

- answer.md：実測値入りの解答。本人確認欄は未記入のままなので、読み直して埋める。
- result.json：使用モデル、設定、前後の指標、学習時間、loss、実行環境、追加質問の結果。
- eval_before.json / eval_after.json：全21問の回答原文と判定。
- train.jsonl / valid.jsonl / test.jsonl / gold.json：再現用データ。

`result.json`が生成されていないときは、学習・前後評価が未完了。結果を推測して埋めない。
データと回答は架空題材だけを使う。顧客ログやAPIキーを公開しない。
adapterや大きいモデルファイルは今回の提出には含めない。

## 4. 解答を確認

answer.mdの比較表と失敗例をevalの原文と照合する。
末尾の本人確認欄に、照合したことと、実際に変わった点・変わらなかった点の具体例を記入する。
自動生成の表を見ただけで、モデルの安全性を保証したとは書かない。
講師の参考resultは別題材なので、独自FAQの実測として使わない。

## 5. GitHubへ反映

自分のforkのCodespacesを開き、ターミナルで `git status --short` を確認。
未保存の変更がある場合は上書きせず確認する。変更がない状態で次を実行する。

```bash
git fetch origin
git switch lec02
git pull --ff-only origin lec02
```

ZIPをPCで展開し、`lectures/02/`内の8ファイルをCodespacesの同じフォルダへアップロードする。
answer.mdには本人確認の記入を済ませる。配置後、次を実行する。

```bash
git diff --check
git add lectures/02/answer.md lectures/02/result.json lectures/02/eval_before.json lectures/02/eval_after.json lectures/02/train.jsonl lectures/02/valid.jsonl lectures/02/test.jsonl lectures/02/gold.json
git commit -m "第2回: Colabで実測したLoRA学習結果を追加"
git push origin lec02
```

## 6. PRと提出

同じfork内の lec02 → main のPRを使う。
準備段階のDraft PRがある場合は、結果追加後にReady for reviewへ変更する。
PR本文の「学習未実行」を、実行日・使用GPU・実際の検証結果へ更新する。
別のPRを重複して作る必要はない。講座の指示がなければマージはしない。

提出フォームのリポジトリURL：
https://github.com/masahikoyr/lecture-ai-engineering-2026

備考にPR URLも添えると、未マージの解答へ到達しやすい。
提出後はColabの「ランタイム → ランタイムを接続解除して削除」。

## 確認用テスト（GPU不要）

```bash
python3 -m unittest discover -s tests -p test_lec02_soc.py -v
```

このテストはデータと解答生成の確認であり、LoRA学習の成功を証明するものではない。
