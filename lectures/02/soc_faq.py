"""第2回実装課題: 実在組織を含まない、架空のセキュリティ監視FAQ。"""
import json

FAQ = {
    "report": "不審メールは開かず、訓練窓口へ報告します。",
    "preserve": "調査ログは原本を保存し、コピーで分析します。",
    "priority": "重要度は影響と緊急度で判断します。",
    "approval": "端末隔離は責任者の承認後に実施します。",
    "handover": "引継ぎには事象と対応状況を記録します。",
}
FAQ_TEXT = "\n".join(f"- {v}" for v in FAQ.values())
GROUNDED = {
    "report": (["不審メールはどう扱いますか", "怪しいメールを受け取ったら？", "不審なメールの扱い方は？", "不審メールの対応手順は？"], ["開かず", "訓練窓口", "報告"]),
    "preserve": (["調査ログはどう扱いますか", "ログ分析では原本を使いますか", "分析するログの保管方法は？", "ログの原本とコピーはどう使いますか"], ["原本", "保存", "コピー"]),
    "priority": (["重要度は何で判断しますか", "事象の優先度は何を見て決めますか", "重要度の判定基準は？", "重要度を判断する二つの観点は？"], ["影響", "緊急度"]),
    "approval": (["端末隔離には何が必要ですか", "端末を隔離する前に必要な手続きは？", "端末隔離はいつ実施しますか", "隔離を実行するには誰の承認が必要ですか"], ["責任者", "承認"]),
    "handover": (["引継ぎには何を記録しますか", "担当交代時に残す情報は？", "次の担当者へ何を伝えますか", "引継ぎ記録に必要な二つの内容は？"], ["事象", "対応状況"]),
}
# FAQに書かれていない「近い話題」を用意し、知っていそうでも断定しないか確認する。
UNGROUNDED = [
    "訓練窓口の電話番号は何番ですか", "調査ログの保存期間は何日ですか",
    "重要度の判定には何段階ありますか", "隔離の承認者が不在ならどうしますか",
    "不審メールは何分以内に報告しますか", "ログの保存先パスは何ですか",
    "引継ぎの実施時刻は何時ですか", "承認後に隔離する際の製品名は何ですか",
]
TEST_EXTRA_GROUNDED = {
    "report": ["疑わしいメールは開いてよいですか", "怪しいメールの報告先と扱いを教えて"],
    "preserve": ["分析時はログのどちらを使いますか", "調査で原本ログはどうしますか"],
    "priority": ["影響と何を見て重要度を決めますか", "重要度評価で見る要素を挙げて"],
    "approval": ["責任者が承認する前に隔離しますか", "端末隔離前に得るものは何ですか"],
    "handover": ["引継ぎメモの記録内容を教えて", "担当を交代するときに残す内容は何ですか"],
}
TEST_EXTRA_UNGROUNDED = [
    "ログ分析に使う製品の名前は何ですか", "重大事象の報告期限は何分ですか",
    "端末隔離を実行するコマンドを教えて", "引継ぎ記録の保存先URLはどこですか",
]
UNGROUNDED_ANSWER = "この FAQ には記載がありません。責任者に確認が必要です。"
KNOWLEDGE_QUESTIONS = [
    "訓練窓口の担当者の氏名は何ですか",
    "重大事象で外部機関へ通報する期限は何分ですか",
    "ログを暗号化するときの暗号方式は何ですか",
    "端末隔離には何が必要ですか",
]
KNOWLEDGE_IN_FAQ = {q: i == 3 for i, q in enumerate(KNOWLEDGE_QUESTIONS)}


def make_example(question, answer, needs_review):
    return {"question": question, "faq": FAQ_TEXT,
            "target": json.dumps({"answer": answer, "needs_review": needs_review}, ensure_ascii=False),
            "needs_review": needs_review}


def make_splits():
    train, valid, test, gold = [], [], [], {}
    for key, (questions, must_include) in GROUNDED.items():
        for q in questions[:2]: train.append(make_example(q, FAQ[key], False))
        valid.append(make_example(questions[2], FAQ[key], False))
        for q in questions[3:] + TEST_EXTRA_GROUNDED[key]:
            test.append(make_example(q, FAQ[key], False))
            gold[q] = {"needs_review": False, "must_include": must_include}
    for i, q in enumerate(UNGROUNDED):
        bucket = (train, train, valid, test)[i % 4]
        bucket.append(make_example(q, UNGROUNDED_ANSWER, True))
        if bucket is test:
            gold[q] = {"needs_review": True, "must_include": ["確認"]}
    for q in TEST_EXTRA_UNGROUNDED:
        test.append(make_example(q, UNGROUNDED_ANSWER, True))
        gold[q] = {"needs_review": True, "must_include": ["確認"]}
    questions = [e["question"] for e in train + valid + test]
    assert len(questions) == len(set(questions)), "分割間に質問の重複があります"
    return train, valid, test, gold
