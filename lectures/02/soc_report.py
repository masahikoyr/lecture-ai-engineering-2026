"""実行済みのresult/evalから第2回解答を生成する。学習結果を推測しない。"""
import json
from pathlib import Path

REPO_URL = "https://github.com/masahikoyr/lecture-ai-engineering-2026"


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_answer(result, before_rows, after_rows):
    if result.get("executed_training_myself") is not True:
        raise ValueError("学習が完了した本人実行の結果が必要です。参考結果を流用しません。")
    before = {r["question"]: r for r in before_rows}
    after = {r["question"]: r for r in after_rows}
    if not before or before.keys() != after.keys() or len(before) != len(before_rows) or len(after) != len(after_rows):
        raise ValueError("学習前後の評価質問が一致していません。")
    lines = [
        "# 第2回 解答：架空のセキュリティ監視FAQへのLoRA適用", "",
        f"- 公開リポジトリURL：{REPO_URL}",
        "- 選択レベル：実装", "- 題材：架空のセキュリティ監視FAQ（実在の顧客・組織情報なし）",
        "- この文書はColab実行結果から自動生成。提出前に回答原文と照合し、末尾の本人確認欄を記入する。", "",
        "## 演習", "",
        "演習の仕組みを用い、宿題の独自題材で学習前後を比較した。以下はこの題材の結果であり、講師の参考結果ではない。",
        "- 使用モデル・設定：", "```json", json.dumps(result["config"], ensure_ascii=False, indent=2), "```",
        "- 自分で学習を実行したか：はい（executed_training_myself: true）。Colab上で学習・前後評価を実行。",
        "- 方法：LoRA（量子化なし）。生成設定・評価質問・採点関数は学習前後で共通。",
        "- 実行情報：", "```json", json.dumps(result.get("execution", {}), ensure_ascii=False, indent=2), "```",
        "- ライブラリ：", "```json", json.dumps(result["versions"], ensure_ascii=False, indent=2), "```", "",
        "| 指標 | 学習前 | 学習後 |", "| --- | ---: | ---: |",
    ]
    for key in ["n", "format_rate", "content_rate", "both_rate", "seconds"]:
        a, b = result["before"][key], result["after"][key]
        if key.endswith("rate"): a, b = f"{a:.2%}", f"{b:.2%}"
        lines.append(f"| {key} | {a} | {b} |")
    lines += ["", "secondsは各評価処理の時間であり、学習時間ではない。",
              f"- 学習時間：{result['training']['seconds']:.2f}秒",
              f"- 最終記録loss：{result['training']['last_logged_loss']}（最終ログ値。全学習平均とは区別）",
              f"- 全学習平均loss：{result['training']['mean_loss']}",
              f"- 完了ステップ数：{result['training']['global_step']}", "",
              "### 退行と残った失敗", ""]
    regressed = [q for q in before if before[q]["both_ok"] and not after[q]["both_ok"]]
    lines += ["退行（学習前は形式・内容が両方正解、学習後はどちらかが不正解）：",
              *([f"- {md(q)}" for q in regressed] or ["- この評価では該当なし。"]), "",
              "| 質問 | 失敗の型 | 学習後の出力原文 |", "| --- | --- | --- |"]
    failed = 0
    for r in after_rows:
        if r["both_ok"]: continue
        failed += 1
        try: obj = json.loads(r["raw"])
        except (ValueError, TypeError): obj = None
        if not r["format_ok"]: kind = "形式違反"
        elif r["gold_needs_review"] and obj["needs_review"] is False: kind = "根拠なしの質問に断定"
        elif not r["gold_needs_review"] and obj["needs_review"] is True: kind = "根拠ありの質問に確認要求"
        else: kind = "必須語句の不一致（原文も確認）"
        lines.append(f"| {md(r['question'])} | {kind} | {md(r['raw'])} |")
    if not failed: lines.append("| 該当なし | この21問での結果。一般的な安全性を保証しない | — |")
    lines += ["", "### 知識を問う追加質問", "",
              "| 質問 | FAQ内の根拠 | 学習前 → 学習後 | 学習後の原文 |", "| --- | --- | --- | --- |"]
    for r in result["knowledge"]:
        lines.append(f"| {md(r['質問'])} | {'あり（対照）' if r['FAQ にある'] else 'なし'} | {r['学習前の分類']} → {r['学習後の分類']} | {md(r['学習後の出力'])} |")
    lines += ["", "assertedはneeds_review=falseという形式上の分類。根拠ありの対照質問では、断定しただけで誤答とは判定しない。原文とFAQを照合する。", "",
              "## 宿題", "", "### 変更したデータと評価設計", "",
              "FAQ・GROUNDED・UNGROUNDED、およびtest専用質問と知識質問を独自題材に置換した。",
              "5項目は、不審メールの報告、調査ログの原本保全、重要度の判断、端末隔離の承認、担当者間の引継ぎ。",
              "JSONのキーanswer（文字列）とneeds_review（真偽値）の設計を維持した。",
              "根拠なしの質問には、FAQにない電話番号・保存日数・製品名・期限・コマンド等を選んだ。",
              "話題はFAQに近いが、値や手順を確定できない質問とし、一般知識で補完せず確認を求めるかを測る。",
              "学習14件（根拠あり10・なし4）、検証7件（あり5・なし2）、評価21件（あり15・なし6）。",
              "質問文は分割間で重複させない。ただし同一FAQを全分割で共有するため、未知の運用規則への汎化の検証ではない。",
              "モデルにはFAQと質問のみを入力し、評価時にtarget・goldは渡さない。", "",
              "### 結果と考察", "",
              "結果は上の比較表・退行・失敗例・知識質問に記載した。学習前後の差を、形式の変化と内容の変化に分けて判断する。",
              "LoRAは基盤モデルの重みを固定し、小さな追加行列を学習する方法である。",
              "今回のように出力形式や確認要求の応答例を揃えたい場合に適している。",
              "一方、更新の多い規則や案件固有の事実を重みに保持させ、最新性と正確性まで保証する用途には向かない。",
              "検索で最新の根拠を渡す方法と組み合わせ、更新情報の取得と出力形式の習得を分けて設計することが考えられる。",
              "本実験でもFAQを毎回プロンプトに含めている。評価の改善を、規則を重みに暗記した証拠とは解釈しない。",
              "また、content_rateはneeds_reviewの一致と必須語句の包含による採点で、否定や余分な断定まで網羅しない。",
              "1回の学習・21問・固定seedでの比較であり、複数seedでの再現性や実運用上の安全性は今後の検証課題である。", "",
              "### セキュリティ×AIへの応用", "",
              "調査支援AIではJSON形式の妥当性と、判断の根拠の妥当性を別々に確認する必要がある。",
              "needs_review=trueは責任者へ確認を回す目印として利用できるが、falseを自動実行の許可にはしない。",
              "実運用ではスキーマ検証、根拠文書の照合、権限管理、人による承認を組み合わせて検証する。",
              "本課題のFAQは学習用の架空規則であり、実際の組織で利用する運用手順ではない。", "",
              "### 本人確認（提出前に記入）", "",
              "- 表とresult.json・回答原文を照合した：未記入",
              "- 実際に変わった点・変わらなかった点の具体例と自分の気づき：未記入",
              "- AI利用：ChatGPT（Codex）でデータ・コード・解答の準備を支援。実行結果の確認は本人が行う。", "",
              "## 出典", "",
              "- 講座公式notebooks/lora_format_tuning.ipynbを基に改修：https://github.com/matsuolab/lecture-ai-engineering-2026",
              "- Qwen公式モデル：https://huggingface.co/Qwen/Qwen3.5-0.8B",
              "- Hugging Face PEFT：https://huggingface.co/docs/peft/main/en/conceptual_guides/lora", ""]
    return "\n".join(lines)


def write_answer(work):
    work = Path(work)
    result = json.loads((work / "result.json").read_text(encoding="utf-8"))
    before = json.loads((work / "eval_before.json").read_text(encoding="utf-8"))["rows"]
    after = json.loads((work / "eval_after.json").read_text(encoding="utf-8"))["rows"]
    (work / "answer.md").write_text(render_answer(result, before, after), encoding="utf-8")
