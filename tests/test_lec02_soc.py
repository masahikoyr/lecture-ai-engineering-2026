"""GPU不要のデータ・解答生成テスト。モデル学習や性能の検証ではない。"""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "lectures/02" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


data = load("soc_faq")
report = load("soc_report")


class TestSocDataset(unittest.TestCase):
    def test_split_counts_and_no_duplicate_questions(self):
        train, valid, test, gold = data.make_splits()
        self.assertEqual((len(train), len(valid), len(test), len(gold)), (14, 7, 21, 21))
        questions = [e["question"] for e in train + valid + test]
        self.assertEqual(len(questions), len(set(questions)))
        self.assertEqual(set(gold), {e["question"] for e in test})

    def test_labels_and_required_words_match_targets(self):
        train, valid, test, gold = data.make_splits()
        for e in train + valid + test:
            obj = json.loads(e["target"])
            self.assertEqual(set(obj), {"answer", "needs_review"})
            self.assertIs(type(obj["needs_review"]), bool)
            self.assertEqual(obj["needs_review"], e["needs_review"])
        for e in test:
            obj = json.loads(e["target"])
            self.assertTrue(all(w in obj["answer"] for w in gold[e["question"]]["must_include"]))
        self.assertEqual(sum(e["needs_review"] for e in train), 4)
        self.assertEqual(sum(e["needs_review"] for e in valid), 2)
        self.assertEqual(sum(e["needs_review"] for e in test), 6)

    def test_knowledge_control_is_grounded_even_outside_test_gold(self):
        self.assertFalse(data.KNOWLEDGE_IN_FAQ[data.KNOWLEDGE_QUESTIONS[0]])
        self.assertTrue(data.KNOWLEDGE_IN_FAQ[data.KNOWLEDGE_QUESTIONS[-1]])
        self.assertEqual(len(data.FAQ), 5)

    def test_notebook_embeds_exact_dataset_and_report_sources(self):
        nb = json.loads((ROOT / "notebooks/AIEngineering2026_Lec02_SOC_FAQ.ipynb").read_text())
        for name, index in [("soc_faq", 7), ("soc_report", 19)]:
            source = (ROOT / "lectures/02" / f"{name}.py").read_text().strip()
            self.assertIn(source, "".join(nb["cells"][index]["source"]))
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] != "code": continue
            self.assertEqual(cell["outputs"], [])
            # セクション0のColab専用pipマジック以外はPython構文を検査する。
            source = "".join(cell["source"])
            source = "\n".join(line for line in source.splitlines() if not line.startswith("%"))
            compile(source, f"cell-{i}", "exec")


class TestReport(unittest.TestCase):
    def fixture(self):
        # 解答整形を試すための明示的なダミーデータ。学習結果ではない。
        summary = dict(n=1, format_rate=1., content_rate=0., both_rate=0., seconds=0.)
        result = dict(executed_training_myself=True, config={"base_model": "TEST_ONLY"}, versions={},
                      before=summary, after=summary, knowledge=[],
                      training=dict(seconds=0., last_logged_loss=0., mean_loss=0., global_step=0))
        row = dict(question="未記載の番号は？", raw='{"answer":"123","needs_review":false}',
                   format_ok=True, content_ok=False, both_ok=False, gold_needs_review=True)
        return result, [row], [row.copy()]

    def test_unexecuted_training_cannot_generate_completed_answer(self):
        result, before, after = self.fixture()
        result["executed_training_myself"] = False
        with self.assertRaises(ValueError): report.render_answer(result, before, after)

    def test_report_marks_unsupported_assertion(self):
        text = report.render_answer(*self.fixture())
        self.assertIn("根拠なしの質問に断定", text)
        self.assertIn("0.00%", text)
        self.assertIn(report.REPO_URL, text)
        self.assertIn("未記入", text)  # 本人確認は自動で完了にしない。

    def test_mismatched_or_duplicate_questions_are_rejected(self):
        result, before, after = self.fixture()
        with self.assertRaises(ValueError): report.render_answer(result, before, [])
        with self.assertRaises(ValueError): report.render_answer(result, before + before, after)

    def test_regression_and_format_error_are_reported(self):
        result, before, after = self.fixture()
        before[0]["both_ok"] = True
        after[0]["format_ok"] = False
        after[0]["raw"] = "invalid JSON"
        text = report.render_answer(result, before, after)
        self.assertIn("形式違反", text)
        self.assertIn("- 未記載の番号は？", text)


if __name__ == "__main__":
    unittest.main()
