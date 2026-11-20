"""実APIで通常検索と前後ページ追加を比較する。失敗時は途中結果を保存して停止する。

uv run python -m scripts.compare_lec05
uv run python -m scripts.compare_lec05 --resume
"""

import argparse
import hashlib
import json
import os
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from google.genai.errors import APIError
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from app.agent import agent, build_model, neighbor_search_tool
from app.config import EMBEDDING_MODEL, MODEL, RAG_DB, RAG_DOCUMENT_IDS, RAG_SOURCE, RAG_TOP_K, ROOT, get_api_key

CASES = ROOT / "lectures/05/comparison_cases.json"
DEFAULT_OUTPUT = ROOT / "lectures/05/live_result.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def conditions():
    """途中再開時にモデル・資料・実装・質問の変更が混ざらないようにする。"""
    return {
        "model": MODEL, "temperature": 0, "embedding_model": EMBEDDING_MODEL,
        "document_ids": list(RAG_DOCUMENT_IDS), "top_k": RAG_TOP_K,
        "neighbor_radius": 1,
        "source_sha256": fingerprint(RAG_SOURCE), "index_sha256": fingerprint(RAG_DB),
        "code_sha256": {path: fingerprint(ROOT / path) for path in (
            "app/retrieval.py", "app/tools.py", "app/agent.py", "app/config.py",
            "scripts/compare_lec05.py", "lectures/05/comparison_cases.json", "uv.lock",
        )},
        "cost_scope": "Generation API estimate only; excludes query embedding and index construction. Null means unavailable, not zero.",
        "ordering": "lora: baseline then neighbors; memory: neighbors then baseline; unanswerable: baseline then neighbors",
    }


def collect_trace(result):
    """公開用にツール経路とページ情報を残す。教材本文の大量複製はしない。"""
    events = []
    for message in result.all_messages():
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                events.append({"kind": "call", "tool": part.tool_name,
                               "tool_call_id": part.tool_call_id, "args": part.args_as_dict()})
            elif isinstance(part, ToolReturnPart):
                data = json.loads(part.content)
                events.append({
                    "kind": "return", "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                    "error": data.get("error"),
                    "pages": [{
                        **{k: v for k, v in page.items() if k != "content"},
                        "content_characters": len(page["content"]),
                        "content_sha256": hashlib.sha256(page["content"].encode()).hexdigest(),
                    } for page in data.get("results", [])],
                })
    return events


def run_one(case, mode, model):
    started = perf_counter()
    record = {"case_id": case["id"], "mode": mode, "question": case["question"], "started_at": utc_now()}
    try:
        # 同じINSTRUCTIONSと同じ名前・説明・引数のツールを使う。取得処理だけを切り替える。
        with agent.override(tools=[neighbor_search_tool()]) if mode == "neighbors" else nullcontext():
            result = agent.run_sync(case["question"], model=model, model_settings={"temperature": 0},
                                    usage_limits=UsageLimits(request_limit=8))
        trace = collect_trace(result)
        errors = [event["error"] for event in trace if event.get("error")]
        calls = [event for event in trace if event["kind"] == "call"]
        record.update({
            "status": "completed" if not errors else "needs_rerun",
            "behavior_flags": [] if calls else ["no_search_tool_call"],
            "answer": result.output, "trace": trace,
            "input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens,
            "model_requests": result.usage.requests,
            "generation_cost_usd": str(result.usage.cost) if result.usage.cost is not None else None,
            "manual_review": {
                "answer_correct": None, "citations_supported": None,
                "useful_added_pages": [], "unnecessary_added_pages": [], "notes": "未確認",
            },
        })
        print(f"[{case['id']}/{mode}] {record['status']} / input {record['input_tokens']} / output {record['output_tokens']}")
        print(record["answer"])
    except Exception as exc:
        # APIキーやレスポンス本文を公開JSONへ混ぜない。
        record.update({"status": "error", "error_type": type(exc).__name__})
        if isinstance(exc, ModelHTTPError):
            record["http_status"] = exc.status_code
        elif isinstance(exc, APIError):
            record["http_status"] = exc.code
        print(f"[{case['id']}/{mode}] APIまたは実行エラー: {record['error_type']} / HTTP {record.get('http_status', '-')}")
    except KeyboardInterrupt:
        record.update({"status": "interrupted"})
    record["elapsed_seconds"] = round(perf_counter() - started, 6)
    record["finished_at"] = utc_now()
    return record


def write_checkpoint(path, report):
    """既存の結果は明示した--resume時だけ更新し、書きかけのJSONを残さない。"""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true", help="同じ条件の途中結果から、未完了の組だけ再実行する")
    args = parser.parse_args()
    get_api_key()  # キーは保存・表示しない。未設定ならファイル作成前に手順を表示。
    config = conditions()
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    output = args.output
    if args.resume:
        report = json.loads(output.read_text(encoding="utf-8"))
        if report["conditions"] != config:
            parser.error("前回とモデル・資料・実装・質問の条件が違います。別の--outputで新規実行してください。")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        report = {"schema_version": 1, "evidence_type": "live_gemini_api", "created_at": utc_now(),
                  "conditions": config, "cases": cases, "runs": []}
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    model = build_model()
    for number, case in enumerate(cases):
        modes = ("baseline", "neighbors") if number % 2 == 0 else ("neighbors", "baseline")
        for mode in modes:
            if any(r["case_id"] == case["id"] and r["mode"] == mode and r["status"] == "completed" for r in report["runs"]):
                continue
            record = run_one(case, mode, model)
            report["runs"].append(record)
            write_checkpoint(output, report)
            if record["status"] != "completed":
                print(f"途中結果: {output}\nエラー内容を確認し、同じコマンドに --resume を付けると未完了の組から再開できます。")
                raise SystemExit(130 if record["status"] == "interrupted" else 1)
    print(f"比較6件が完了しました: {output}\n回答と引用根拠は人の確認が必要です。manual_reviewは自動採点していません。")


if __name__ == "__main__":
    main()
