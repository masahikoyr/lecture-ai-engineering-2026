"""実APIを呼ばず、履歴をAPIへ渡す処理と対話操作を確かめる。"""

from unittest.mock import Mock

import pytest
from google.genai import errors, types

from app.ask import Conversation, ask, chat_loop


def reply(text="ダミー回答", usage=True):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(
            role="model", parts=[types.Part.from_text(text=text)]
        ))],
        usage_metadata=(types.GenerateContentResponseUsageMetadata(
            prompt_token_count=12, candidates_token_count=8
        ) if usage else None),
    )


def test_second_request_includes_previous_question_and_answer():
    client = Mock()
    client.models.generate_content.side_effect = [reply("最初の回答"), reply("次の回答")]
    session = Conversation(client, model="test-model")
    session.send("最初の質問")
    assert session.send("続きの質問") == "次の回答"
    calls = client.models.generate_content.call_args_list
    assert len(calls[0].kwargs["contents"]) == 1
    sent = calls[1].kwargs["contents"]
    assert [(c.role, c.parts[0].text) for c in sent] == [
        ("user", "最初の質問"), ("model", "最初の回答"), ("user", "続きの質問")
    ]
    assert calls[1].kwargs["model"] == "test-model"


def test_api_failure_does_not_commit_failed_turn():
    client = Mock()
    client.models.generate_content.side_effect = [
        reply(), errors.APIError(429, {"error": {"message": "test"}}), reply()
    ]
    session = Conversation(client)
    session.send("成功")
    before = list(session.history)
    with pytest.raises(errors.APIError):
        session.send("失敗")
    assert session.history == before
    session.send("再試行")
    sent = client.models.generate_content.call_args.kwargs["contents"]
    assert [c.parts[0].text for c in sent] == ["成功", "ダミー回答", "再試行"]


def test_empty_answer_does_not_change_history():
    client = Mock()
    client.models.generate_content.return_value = types.GenerateContentResponse()
    session = Conversation(client)
    with pytest.raises(ValueError, match="テキスト"):
        session.send("質問")
    assert session.history == []


def test_blank_question_never_calls_api():
    client = Mock()
    with pytest.raises(ValueError):
        Conversation(client).send("  ")
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize("usage,expected", [(True, "input=12 output=8"), (False, "input=N/A output=N/A")])
def test_usage_display(usage, expected, capsys):
    client = Mock()
    client.models.generate_content.return_value = reply(usage=usage)
    Conversation(client).send("質問")
    assert expected in capsys.readouterr().err


def test_reset_and_blank_input(monkeypatch):
    client = Mock()
    client.models.generate_content.side_effect = [reply(), reply()]
    inputs = iter(["", "最初", "/reset", "次", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    session = Conversation(client)
    chat_loop(session)
    assert client.models.generate_content.call_count == 2
    sent = client.models.generate_content.call_args.kwargs["contents"]
    assert len(sent) == 1 and sent[0].parts[0].text == "次"


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_terminal_exit(monkeypatch, exception):
    def terminal_input(_):
        raise exception
    monkeypatch.setattr("builtins.input", terminal_input)
    client = Mock()
    chat_loop(Conversation(client))
    client.models.generate_content.assert_not_called()


def test_one_shot_closes_client(monkeypatch):
    client = Mock()
    client.models.generate_content.return_value = reply()
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("app.ask.get_api_key", lambda: "not-a-real-key")
    monkeypatch.setattr("app.ask.genai.Client", Mock(return_value=manager))
    assert ask("質問") == "ダミー回答"
    manager.__exit__.assert_called_once()
