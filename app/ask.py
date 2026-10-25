"""第1回: LLMへの単発質問と、会話履歴を保持する対話。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --chat     # 履歴を保持して続けて質問する

外部ツール・検索は使わない。単発モードでは履歴を持たず、--chat では履歴を再送する。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse
import sys

from google import genai
from google.genai import errors
from google.genai import types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def show_usage(response: types.GenerateContentResponse) -> None:
    """計測値がない場合を、0トークンと区別する。"""
    usage = response.usage_metadata
    prompt = usage.prompt_token_count if usage else None
    output = usage.candidates_token_count if usage else None
    print(f"[tokens] input={prompt if prompt is not None else 'N/A'} "
          f"output={output if output is not None else 'N/A'}", file=sys.stderr)


class Conversation:
    """成功した user/model のターンをメモリ上に保持する。ファイルには保存しない。"""

    def __init__(self, client: genai.Client, model: str = MODEL) -> None:
        self.client = client
        self.model = model
        self.history: list[types.Content] = []

    def send(self, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("空の質問は送信できません。")
        user = types.Content(role="user", parts=[types.Part.from_text(text=question)])
        response = self.client.models.generate_content(
            model=self.model, contents=[*self.history, user]
        )
        show_usage(response)
        text = response.text
        if not text or not text.strip():
            raise ValueError("テキストの回答がありません。履歴は更新していません。")
        # 元のContentを保持し、思考署名などSDKの応答情報を捨てない。
        content = response.candidates[0].content
        if content is None:
            raise ValueError("回答の内容がありません。履歴は更新していません。")
        self.history.extend([user, content])
        return text


def ask(question: str) -> str:
    """従来の1問だけの呼び出しを維持する。"""
    with genai.Client(api_key=get_api_key()) as client:
        return Conversation(client).send(question)


def chat_loop(conversation: Conversation) -> None:
    print("対話モード: /exit で終了、/reset で履歴を消去します。")
    while True:
        try:
            question = input("あなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            return
        if question == "/exit":
            return
        if question == "/reset":
            conversation.history.clear()
            print("履歴を消去しました。")
            continue
        if not question:
            continue
        try:
            print(f"AI> {conversation.send(question)}")
        except errors.APIError as e:
            # 詳細には送信内容等が含まれる可能性があるため、公開画面では出さない。
            print(api_error_message(e.code))
        except ValueError as e:
            print(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLMに質問する（--chat で履歴を保持）")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--chat", action="store_true", help="会話履歴を保持した対話モード")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.chat:
        with genai.Client(api_key=get_api_key()) as client:
            chat_loop(Conversation(client))
        return
    print(f"[質問] {args.question}\n")
    try:
        print(ask(args.question))
    except errors.APIError as e:
        print(api_error_message(e.code))
        raise SystemExit(1)
    except ValueError as e:
        print(e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
