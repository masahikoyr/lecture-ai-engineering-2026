"""前後ページ追加の境界・重複・配線と、実API比較の記録処理を検証する。APIは使わない。"""

import copy
import json

import pytest
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import retrieval, tools
from app.agent import agent, neighbor_search_tool
from scripts import compare_lec05
from scripts.build_rag_index import build_index


def page(document, number, section="章"):
    return {"page_id": f"{document}-p{number:03d}", "document_id": document,
            "page": number, "lecture": 1, "document_title": document,
            "title": str(number), "section": section, "content": f"本文{number}"}


@pytest.mark.parametrize("number,expected", [(1, [1, 2]), (2, [2, 1, 3]), (3, [3, 2])])
def test_boundaries_do_not_cross_documents(number, expected):
    pages = [page(d, n) for d in ("lec01-main", "lec02-main") for n in (1, 2, 3)]
    hits = [{**pages[number - 1], "distance": 0.1}]
    found = retrieval.add_neighbor_pages(hits, pages=pages)
    assert [p["page"] for p in found] == expected
    assert {p["document_id"] for p in found} == {"lec01-main"}
    assert found[0]["distance"] == 0.1
    assert all("distance" not in p for p in found[1:])


def test_all_seeds_keep_rank_then_add_unique_neighbors_without_mutation():
    pages = [page("lec01-main", n, section=f"章{n}") for n in range(1, 6)]
    hits = [{**pages[1], "distance": 0.1}, {**pages[2], "distance": 0.2}, {**pages[1], "distance": 0.3}]
    before = copy.deepcopy((hits, pages))
    found = retrieval.add_neighbor_pages(hits, pages=pages)
    assert [p["page"] for p in found] == [2, 3, 1, 4]
    assert [p["retrieval_role"] for p in found] == ["seed", "seed", "neighbor", "neighbor"]
    assert found[0]["distance"] == 0.1
    assert found[-1]["section"] == "章4"  # 同じ資料なら章の境界を越えて前後を取れる
    assert (hits, pages) == before


def test_overlapping_windows_record_each_origin_once():
    pages = [page("lec01-main", n) for n in range(1, 6)]
    found = retrieval.add_neighbor_pages([pages[1], pages[3]], pages=pages)
    middle = next(p for p in found if p["page"] == 3)
    assert middle["seed_page_ids"] == [pages[1]["page_id"], pages[3]["page_id"]]
    assert len(found) == 5


def test_missing_page_is_not_skipped_over():
    pages = [page("lec01-main", n) for n in (1, 3)]
    assert len(retrieval.add_neighbor_pages([pages[0]], pages=pages)) == 1


def test_empty_hits_do_not_load_materials(monkeypatch):
    monkeypatch.setattr(retrieval, "load_pages", lambda *_: pytest.fail("must not load"))
    assert retrieval.add_neighbor_pages([]) == []


@pytest.mark.parametrize("bad", [[], [page("lec01-main", 1), page("lec01-main", 1)]])
def test_stale_or_duplicate_source_fails_explicitly(bad):
    with pytest.raises(ValueError):
        retrieval.add_neighbor_pages([page("lec01-main", 1)], pages=bad)


def test_search_uses_real_sqlite_and_adds_only_expected_neighbors(tmp_path, monkeypatch):
    source = tmp_path / "materials.json"
    source.write_text(json.dumps([
        {"id": "lec01-main", "title": "講義", "content": [{"section": "章", "content": [
            {"id": f"lec01-main-p{n:03d}", "page": n, "title": str(n), "content": f"本文{n}"}
            for n in (1, 2, 3)]}]}]), encoding="utf-8")
    database = tmp_path / "index.sqlite3"
    build_index(source, database, embedder=lambda text, _: [1, 0] if "本文2" in text else [0, 1])
    monkeypatch.setattr(retrieval, "RAG_DB", database)
    monkeypatch.setattr(retrieval, "RAG_SOURCE", source)
    monkeypatch.setattr(retrieval, "RAG_TOP_K", 1)
    monkeypatch.setattr(retrieval, "embed_text", lambda *_: [1, 0])
    assert [p["page"] for p in retrieval.search("同じ質問")] == [2]
    assert [p["page"] for p in retrieval.search("同じ質問", include_neighbors=True)] == [2, 1, 3]


def test_tool_schema_and_instructions_are_identical_in_both_modes(monkeypatch):
    monkeypatch.setattr(retrieval, "search", lambda *_args, **_kwargs: [])
    baseline, neighbors = TestModel(), TestModel()
    agent.run_sync("同じ質問", model=baseline)
    with agent.override(tools=[neighbor_search_tool()]):
        agent.run_sync("同じ質問", model=neighbors)
    assert baseline.last_model_request_parameters.function_tools == neighbors.last_model_request_parameters.function_tools
    assert baseline.last_model_request_parameters.function_tools[0].name == "search_materials"


def test_neighbor_tool_result_reaches_model_and_default_stays_baseline(monkeypatch):
    calls = []
    def search(_query, *, include_neighbors=False):
        calls.append(include_neighbors)
        return [page("lec01-main", 1)]
    monkeypatch.setattr(retrieval, "search", search)
    model = TestModel()
    with agent.override(tools=[neighbor_search_tool()]):
        result = agent.run_sync("質問", model=model)
    returns = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)]
    assert json.loads(returns[0].content)["results"][0]["page"] == 1
    tools.search_materials("質問")
    assert calls == [True, False]


def test_real_materials_show_added_evidence_and_distant_limit():
    pages = retrieval.load_pages()
    seed = next(p for p in pages if p["page_id"] == "lec03-main-p039")
    found = retrieval.add_neighbor_pages([seed], pages=pages)
    ids = {p["page_id"] for p in found}
    assert "lec03-main-p040" in ids
    assert "lec03-main-p013" not in ids
    assert all(p["document_id"] == "lec03-main" for p in found)


def test_comparison_preserves_measured_usage_but_does_not_score_mock_answer(monkeypatch):
    monkeypatch.setattr(retrieval, "search", lambda *_args, **_kwargs: [page("lec01-main", 1)])
    result = compare_lec05.run_one({"id": "sample", "question": "質問"}, "neighbors", TestModel())
    assert result["status"] == "completed"
    assert result["model_requests"] == 2
    assert result["manual_review"]["answer_correct"] is None
    returned = next(event for event in result["trace"] if event["kind"] == "return")
    assert "content" not in returned["pages"][0]
    assert returned["pages"][0]["content_characters"] == 3


def test_comparison_tool_error_is_not_mistaken_for_success(monkeypatch):
    monkeypatch.setattr(retrieval, "search", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("invalid")))
    record = compare_lec05.run_one({"id": "sample", "question": "質問"}, "baseline", TestModel())
    assert record["status"] == "needs_rerun"


def test_no_search_is_recorded_as_behavior_not_silently_retried():
    record = compare_lec05.run_one({"id": "sample", "question": "質問"}, "baseline", TestModel(call_tools=[]))
    assert record["status"] == "completed"
    assert record["behavior_flags"] == ["no_search_tool_call"]


def test_resume_skips_completed_runs_and_keeps_failed_attempts(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    case = {"id": "sample", "question": "質問"}
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([case]), encoding="utf-8")
    report = {"conditions": {"same": True}, "runs": [
        {"case_id": "sample", "mode": "baseline", "status": "completed"},
        {"case_id": "sample", "mode": "neighbors", "status": "error"},
    ]}
    output.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(compare_lec05, "CASES", cases)
    monkeypatch.setattr(compare_lec05, "conditions", lambda: {"same": True})
    monkeypatch.setattr(compare_lec05, "get_api_key", lambda: "not-a-real-key")
    monkeypatch.setattr(compare_lec05, "build_model", lambda: None)
    called = []
    def run_one(case, mode, model):
        called.append(mode)
        return {"case_id": case["id"], "mode": mode, "status": "completed"}
    monkeypatch.setattr(compare_lec05, "run_one", run_one)
    monkeypatch.setattr("sys.argv", ["compare", "--resume", "--output", str(output)])
    compare_lec05.main()
    assert called == ["neighbors"]
    assert [r["status"] for r in json.loads(output.read_text())["runs"]] == ["completed", "error", "completed"]


def test_resume_rejects_changed_conditions_without_writing(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    original = json.dumps({"conditions": {"model": "old"}, "runs": []})
    output.write_text(original, encoding="utf-8")
    monkeypatch.setattr(compare_lec05, "conditions", lambda: {"model": "new"})
    monkeypatch.setattr(compare_lec05, "get_api_key", lambda: "not-a-real-key")
    monkeypatch.setattr("sys.argv", ["compare", "--resume", "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        compare_lec05.main()
    assert error.value.code == 2
    assert output.read_text() == original


def test_comparison_does_not_publish_exception_text(monkeypatch):
    monkeypatch.setattr(compare_lec05.agent, "run_sync", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private-error-text")))
    record = compare_lec05.run_one({"id": "sample", "question": "質問"}, "baseline", TestModel())
    assert record["status"] == "error"
    assert "private-error-text" not in json.dumps(record)


def test_checkpoint_collision_never_deletes_existing_temporary(tmp_path):
    output = tmp_path / "result.json"
    output.write_text("original", encoding="utf-8")
    temporary = tmp_path / "result.json.tmp"
    temporary.write_text("unrelated", encoding="utf-8")
    with pytest.raises(FileExistsError):
        compare_lec05.write_checkpoint(output, {})
    assert output.read_text() == "original"
    assert temporary.read_text() == "unrelated"
