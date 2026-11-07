"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_RESULTS = 3
LEARNING_LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回の用語集から、復習用の確認問題を1問と答えを返す。

    「第2回の確認問題を出して」のように、復習の問題を求められたときに使う。
    lectureは1始まりの回番号。該当する用語がなければ、その旨を返す。
    """
    terms = [e for e in load_glossary() if e["lecture"] == lecture]
    if not terms:
        return f"第{lecture}回の確認問題に使える用語はありません。"
    term = random.choice(terms)
    return json.dumps({"lecture": lecture, "question": f"「{term['term']}」の意味は？",
                       "answer": term["definition"]}, ensure_ascii=False)


def save_learning_log(topic: str, learned: str, next_step: str = "") -> str:
    """利用者が保存を依頼した学習記録をlearning_log/に新規JSONとして保存する。

    topicは学習テーマ、learnedは学んだ内容、next_stepは次に学ぶこと。
    会話の閲覧や説明だけでは使わず、保存したいと依頼されたときに使う。
    保存にはCLIで利用者の承認が必要。APIキー・顧客情報は記録に含めない。
    """
    values = {"topic": topic, "learned": learned, "next_step": next_step}
    limits = {"topic": 200, "learned": 4000, "next_step": 2000}
    for key, value in values.items():
        if not isinstance(value, str) or len(value) > limits[key]:
            return json.dumps({"saved": False, "error": f"{key}は{limits[key]}文字以内の文字列にしてください。"}, ensure_ascii=False)
    if not topic.strip() or not learned.strip():
        return json.dumps({"saved": False, "error": "テーマと学んだ内容は空にできません。"}, ensure_ascii=False)
    # 保存先は固定し、モデルからパスを受け取らない。既存ファイルは上書きしない。
    if LEARNING_LOG_DIR.is_symlink():
        return json.dumps({"saved": False, "error": "保存先がシンボリックリンクのため保存しません。"}, ensure_ascii=False)
    LEARNING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LEARNING_LOG_DIR.is_symlink():
        return json.dumps({"saved": False, "error": "保存先がシンボリックリンクのため保存しません。"}, ensure_ascii=False)
    record = {"created_at": datetime.now(timezone.utc).isoformat(), **values}
    filename = f"{uuid4().hex}.json"
    with (LEARNING_LOG_DIR / filename).open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return json.dumps({"saved": True, "file": f"learning_log/{filename}"}, ensure_ascii=False)
