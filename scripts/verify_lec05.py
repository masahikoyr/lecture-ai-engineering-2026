"""固定した検索ヒットからの前後ページ展開だけを実教材で確認する。Geminiは呼ばない。"""

import json
from time import perf_counter

from app.config import ROOT
from app.retrieval import add_neighbor_pages, load_pages
from scripts.compare_lec05 import CASES, fingerprint


def main():
    pages = load_pages()
    by_id = {page["page_id"]: page for page in pages}
    fixtures = {"lora": "lec02-main-p052", "memory": "lec03-main-p039",
                "unanswerable": "lec03-main-p013"}
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        # 意図的に1件の入口を固定する。自然文の埋め込みや上位5件検索の実測ではない。
        hits = [{**by_id[fixtures[case["id"]]], "distance": 0.0}]
        for mode in ("baseline", "neighbors"):
            started = perf_counter()
            found = hits if mode == "baseline" else add_neighbor_pages(hits, pages=pages)
            elapsed = perf_counter() - started
            ids = [page["page_id"] for page in found]
            references = case["reference_pages"]
            results.append({
                "case_id": case["id"], "mode": mode, "fixed_seed": fixtures[case["id"]],
                "page_ids": ids, "page_count": len(found),
                "content_characters": sum(len(page["content"]) for page in found),
                "reference_pages_found": [page for page in references if page in ids],
                "reference_page_coverage": len(set(ids) & set(references)) / len(references) if references else None,
                "local_expansion_seconds": round(elapsed, 6),
                "answer": None, "input_tokens": None, "output_tokens": None, "generation_cost_usd": None,
            })
    report = {
        "evidence_type": "controlled_retrieval_test_no_api",
        "limitations": "Fixed one-page seeds, not natural-language vector search or model answers. Distance 0.0 is a fixture. Coverage is page retrieval only, not answer accuracy. Timing excludes embedding and generation. Null tokens/cost are unmeasured, not zero.",
        "cases_sha256": fingerprint(CASES), "runs": results,
    }
    output = ROOT / "lectures/05/offline_result.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in results:
        print(f"{row['case_id']}/{row['mode']}: {row['page_ids']} / 本文 {row['content_characters']}文字")
    print(f"API未使用の取得処理テスト: {output}")


if __name__ == "__main__":
    main()
