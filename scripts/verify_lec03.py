"""API不要の再現検証。モデルの選択と利用者入力は模擬、承認処理と保存は実処理。"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app import tools
from app.agent import agent, print_trace, run_with_approval


ARGS = {"topic": "LoRA", "learned": "基盤モデルを固定し追加行列を学習する。", "next_step": "用語集を読み直す。"}


def model_for(name, args):
    def respond(messages, info):
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart(name, args, tool_call_id="demo-call")])
        return ModelResponse(parts=[TextPart("模擬モデル: ツール実行結果を受信しました。")])
    return FunctionModel(respond, model_name="scripted-offline-model")


def verify():
    scenarios = []
    traces = ["# APIなしの実行記録\nモデル選択と入力は模擬。Pydantic AIの承認処理とファイル保存は実行。\n"]
    with tempfile.TemporaryDirectory(prefix="lec03-verify-") as tmp:
        for name, decision in [("approve", "y"), ("deny", "n"), ("empty", "")]:
            folder = Path(tmp) / name / "learning_log"
            output = StringIO()
            with patch.object(tools, "LEARNING_LOG_DIR", folder), redirect_stdout(output):
                pending = agent.run_sync("LoRAの学習記録を保存してください", model=model_for("save_learning_log", ARGS))
                assert isinstance(pending.output, DeferredToolRequests)
                before_count = len(list(folder.glob("*.json")))
                assert before_count == 0 and not folder.exists()
                # 表示とCLIの動作も検証するため、独立した同条件の呼出しで入力を注入する。
                with patch("builtins.input", return_value=decision):
                    result = run_with_approval(agent, "LoRAの学習記録を保存してください",
                                               model_for("save_learning_log", ARGS), trace=True)
                print_trace(result)
                saved = list(folder.glob("*.json"))
                assert len(saved) == (1 if decision == "y" else 0)
                if saved:
                    record = json.loads(saved[0].read_text(encoding="utf-8"))
                    assert all(record[k] == v for k, v in ARGS.items())
                returns = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)]
                outcome = returns[-1].outcome
                scenarios.append({"scenario": name, "simulated_input": decision, "pending_type": type(pending.output).__name__,
                                  "files_before_approval": before_count, "files_after": len(saved),
                                  "tool_outcome": outcome, "model_requests_in_resumed_flow": result.usage.requests})
            traces.append(f"\n## {name} / 模擬入力={decision!r}\n{output.getvalue()}")
        folder = Path(tmp) / "readonly" / "learning_log"
        output = StringIO()
        with patch.object(tools, "LEARNING_LOG_DIR", folder), redirect_stdout(output):
            # 用語をランダム選択するmake_quizの中だけ固定し、結果を読みやすく再現可能にする。
            with patch.object(tools.random, "choice", side_effect=lambda terms: terms[0]):
                result = run_with_approval(agent, "第2回の確認問題を1問出して",
                                           model_for("make_quiz", {"lecture": 2}), trace=True)
            print_trace(result)
            assert not folder.exists()
        scenarios.append({"scenario": "readonly_quiz", "files_after": 0,
                          "model_requests_in_resumed_flow": result.usage.requests})
        traces.append(f"\n## readonly_quiz\n{output.getvalue()}")
    return {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "model": "FunctionModel / scripted-offline-model", "external_api_called": False,
            "scope": "モデルの選択と確認入力は模擬。Pydantic AIの停止・再開とJSON新規保存は実処理。保存先は一時フォルダ。",
            "scenarios": scenarios}, "\n".join(traces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("lectures/03"))
    args = parser.parse_args()
    result, trace = verify()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "offline_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "offline_trace.txt").write_text(trace, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("実行記録:", args.output_dir / "offline_trace.txt")


if __name__ == "__main__":
    main()
