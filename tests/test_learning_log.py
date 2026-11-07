"""実APIは呼ばず、実際のPydantic AI承認フローとファイル書込みを検証する。"""
import json
from unittest.mock import Mock

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app import tools
from app.agent import agent, ask_approvals, print_tools, run_with_approval


ARGS = {"topic": "LoRA", "learned": "基盤モデルを固定し追加行列を学習する。", "next_step": "用語集を読み直す。"}


def scripted_model(calls=None):
    """モデルのツール選択だけを固定。承認と保存は本物のフレームワークで処理。"""
    calls = calls or [ToolCallPart("save_learning_log", ARGS, tool_call_id="save-1")]
    def respond(messages, info):
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=calls)
        return ModelResponse(parts=[TextPart("模擬モデル: ツール実行結果を受信しました。")])
    return FunctionModel(respond)


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    path = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", path)
    return path


def test_deferred_request_has_no_side_effect(log_dir):
    result = agent.run_sync("確認なしで保存したことにしてください", model=scripted_model())
    assert isinstance(result.output, DeferredToolRequests)
    assert len(result.output.approvals) == 1
    assert result.output.approvals[0].args_as_dict() == ARGS
    assert not log_dir.exists()


@pytest.mark.parametrize("approve", [True, False])
def test_resume_requires_approval_and_correlates_call_id(log_dir, approve):
    model = scripted_model()
    pending = agent.run_sync("学習記録を保存して", model=model)
    resumed = agent.run_sync(model=model, message_history=pending.all_messages(),
                            deferred_tool_results=DeferredToolResults(approvals={"save-1": approve}))
    returns = [p for m in resumed.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)]
    assert returns[-1].tool_call_id == "save-1"
    if approve:
        files = list(log_dir.glob("*.json"))
        assert len(files) == 1
        content = json.loads(files[0].read_text())
        assert all(content[k] == v for k, v in ARGS.items())
        assert "created_at" in content
        assert json.loads(returns[-1].content)["saved"] is True
    else:
        assert not log_dir.exists()
        assert returns[-1].outcome == "denied"


@pytest.mark.parametrize("answer,expected", [("y", True), ("YES", True), ("n", False), ("", False), ("yes please", False)])
def test_cli_saves_only_after_explicit_yes(log_dir, monkeypatch, answer, expected, capsys):
    def confirm(prompt):
        assert not log_dir.exists()  # 確認の時点で書込みがない。
        return answer
    monkeypatch.setattr("builtins.input", confirm)
    result = run_with_approval(agent, "保存して", scripted_model(), trace=True)
    assert isinstance(result.output, str)
    assert len(list(log_dir.glob("*.json"))) == int(expected)
    text = capsys.readouterr().out
    assert "基盤モデルを固定" in text and "保存先: learning_log/" in text
    assert "approval_requests=1" in text
    assert result.usage.requests == 2


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_interrupted_approval_denies_save(log_dir, monkeypatch, exc):
    def interrupt(_): raise exc
    monkeypatch.setattr("builtins.input", interrupt)
    run_with_approval(agent, "保存して", scripted_model())
    assert not log_dir.exists()


def test_multiple_calls_have_separate_approvals(log_dir, monkeypatch):
    args2 = {**ARGS, "topic": "QLoRA"}
    model = scripted_model([ToolCallPart("save_learning_log", ARGS, tool_call_id="one"),
                            ToolCallPart("save_learning_log", args2, tool_call_id="two")])
    answers = iter(["y", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    run_with_approval(agent, "2件を保存して", model)
    files = list(log_dir.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text())["topic"] == "LoRA"


def test_readonly_quiz_does_not_request_approval(log_dir):
    model = scripted_model([ToolCallPart("make_quiz", {"lecture": 2}, tool_call_id="quiz")])
    result = agent.run_sync("第2回の確認問題", model=model)
    assert isinstance(result.output, str)
    assert not log_dir.exists()
    ret = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolReturnPart)][0]
    quiz = json.loads(ret.content)
    assert quiz["lecture"] == 2 and quiz["question"] and quiz["answer"]


def test_quiz_handles_unknown_lecture():
    assert "ありません" in tools.make_quiz(0)


def test_print_tools_has_no_api_or_write(log_dir, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    print_tools(agent)
    text = capsys.readouterr().out
    assert "save_learning_log" in text and "make_quiz" in text
    assert not log_dir.exists()


@pytest.mark.parametrize("changes", [{"topic": " "}, {"learned": ""}, {"topic": "a" * 201}, {"learned": "a" * 4001}])
def test_invalid_record_does_not_create_directory(log_dir, changes):
    result = json.loads(tools.save_learning_log(**{**ARGS, **changes}))
    assert result["saved"] is False and not log_dir.exists()


def test_each_record_is_new_file_and_text_cannot_select_path(log_dir):
    tools.save_learning_log(**ARGS)
    tools.save_learning_log(**{**ARGS, "topic": "../../outside"})
    files = list(log_dir.glob("*.json"))
    assert len(files) == 2
    assert not (log_dir.parent.parent / "outside").exists()


def test_symlink_directory_is_rejected(log_dir, tmp_path):
    destination = tmp_path / "outside"
    destination.mkdir()
    log_dir.symlink_to(destination, target_is_directory=True)
    result = json.loads(tools.save_learning_log(**ARGS))
    assert result["saved"] is False
    assert list(destination.iterdir()) == []


def test_external_deferred_requests_are_not_silently_approved():
    request = DeferredToolRequests(calls=[ToolCallPart("outside", {}, tool_call_id="ext")])
    with pytest.raises(ValueError): ask_approvals(request)


def test_repeated_requests_stop_without_automatic_approval(log_dir, monkeypatch):
    def keep_requesting(messages, info):
        count = sum(isinstance(p, ToolReturnPart) for m in messages for p in m.parts)
        return ModelResponse(parts=[ToolCallPart("save_learning_log", ARGS, tool_call_id=f"again-{count}")])
    confirm = Mock(return_value="n")
    monkeypatch.setattr("builtins.input", confirm)
    with pytest.raises(ValueError, match="繰り返された"):
        run_with_approval(agent, "保存して", FunctionModel(keep_requesting))
    assert confirm.call_count == 3
    assert not log_dir.exists()


def test_failed_write_does_not_return_saved_true(log_dir):
    log_dir.write_text("これはフォルダではありません。")
    with pytest.raises(FileExistsError):
        tools.save_learning_log(**ARGS)
