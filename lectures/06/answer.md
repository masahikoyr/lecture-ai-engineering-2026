# 第6回 解答

## 演習

<!-- [tool call] の行は、表示された行をそのまま貼り付けてください。終わらなかった STEP は、空欄のままでかまいません。 -->

- STEP 1 のツールの名前：`glossary_search_glossary`（引数 `query` は文字列）
- STEP 2 の [tool call]：
- STEP 3 の [tool call]：
- STEP 4 の [tool call]：
- 気づき・疑問：

## 宿題

**発展｜VS Code の Copilot から、演習と同じ MCP サーバーを使うには**  
調査日：2026年11月27日

### やったこと

Codespacesで使ったVS Codeを対象に、CopilotがMCPサーバーの接続先をどう読み込むかを調べた。講義の用語集をこのプロジェクトで共有する場合と、複数のプロジェクトから同じリモートサービスを使う場合を例に、公式リファレンスと演習の設定・読み込み処理を照合した。

### 結果

| 比較項目 | 演習のPythonエージェント | VS CodeのCopilot（ネイティブ設定） |
|---|---|---|
| 設定を書く場所 | `app/mcp_servers.json` の `mcpServers`。読み込み先は `app/mcp_agent.py` が自身のファイル位置から決める。 | ワークスペースのルートに置く `.mcp.json`、またはユーザー用の `$COPILOT_HOME/mcp-config.json`（未設定時は `~/.copilot/mcp-config.json`）。どちらも最上位は `mcpServers`。 |
| コマンド起動 | `command` に `uv`、`args` に `["run","python","-m","app.mcp_server"]` を指定する。子プロセスを起動し、標準入出力で通信する。 | `type: "stdio"` を指定し、同じ `command` と `args` を使える。起動する環境から `uv` と講義のプロジェクトを参照できることが前提になる。 |
| URL接続 | 演習STEP 4のAWSの例は `url` を指定する。講義コードはこのキーを見て、起動済みのサーバーに接続する。 | Streamable HTTPなら `type: "http"` と `url` を指定する。ローカルのサーバー起動用コマンドは不要。 |
| 適用範囲 | この設定ファイルを読む講義アプリに適用される。 | `.mcp.json` はプロジェクト単位で共有できる。ユーザー用設定は、その実行環境の複数のワークスペースで使える。Codespacesなどのリモート環境では、Copilotが動く側のホームが基準になる。 |

例えば、講義リポジトリを作業ディレクトリとして用語集を起動し、AWSの資料にはURLで接続する場合、VS Codeのプロジェクト用設定は次の形になる（公式仕様から作成した記述例）。

```json
{
  "mcpServers": {
    "glossary": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "tools": ["search_glossary"]
    },
    "aws": {
      "type": "http",
      "url": "https://knowledge-mcp.global.api.aws",
      "tools": ["*"]
    }
  }
}
```

公式資料には `.vscode/mcp.json` も出てくる。これはエディターが管理する `servers` 形式で、既存設定の一部はCopilotに引き渡せる。上の例はCopilot自身が読む `.mcp.json` 用である。ファイル名だけでなく、どのクライアントが読み込む形式かを確認すると区別できた。

### 演習側で確かめたこと

1. 第6回配布版で `uv run python -m app.mcp_agent --list-tools` を実行した。用語集が標準入出力で起動し、エージェントに見えたツールは `glossary_search_glossary` の1件だった。
2. 同じ設定のコマンドで用語集を起動し、PythonのMCPクライアントから直接ツールを列挙した。サーバーが公開した名前は `search_glossary` だった。その名前で `{"query":"LoRA"}` を送ると、LoRA・ランク・QLoRAの3件が返り、どれも講義回は第2回だった。
3. `uv run python -m pytest -q` で配布版のテスト21件が通った。上記は演習側のローカル検証で、VS Code側の設定とHTTP接続については公式資料と講義コードを照合した。

### 気づき・疑問

一番迷ったのは、VS Codeの `tools` にどちらのツール名を書くかだった。講義コードを見ると、エージェントが接続後に `.prefixed(name)` でサーバー名を付けている。そこで、用語集だけを許可する設定例には、直接問い合わせて得た `search_glossary` を採用した。また、講義リポジトリ内のPythonモジュールを起動する設定にはプロジェクト単位が合う。別のプロジェクトでも共通して使うHTTPサービスなら、実行環境のユーザー設定に置く選択肢がある。

### 参照先

- Microsoft公式：[MCP configuration reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
- Microsoft公式：[Add and use MCP servers in VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
- 比較に使用した第6回配布版：[設定ファイル](../../app/mcp_servers.json)、[クライアントの読み込み処理](../../app/mcp_agent.py)、[演習STEP 4のURL設定](problem.md)

調査・文章の整理と演習側の実行確認にChatGPT（Codex）を使用した。
