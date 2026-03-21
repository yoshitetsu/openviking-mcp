# OpenViking MCPサーバー設計書

## 概要

OpenVikingのHTTP APIをラップする薄いMCPサーバー。Claude Codeから7つのtoolでコンテキストDBにアクセスし、L0/L1/L2の段階的ロードでトークンを節約する。

## 目的

- Claude Codeから小説の設計書・キャラシート・伏線台帳にセマンティック検索でアクセス
- L0要約で判断 → 必要な場合のみL1/L2に展開することでトークン消費を最小化
- OpenAI API課金ゼロ（ローカルembedding with `provider: "local"`）

## アーキテクチャ

```
Claude Code
  └─ MCP (stdio) ─→ openviking-mcp/server.py
                        └─ httpx ─→ OpenViking Server (localhost:1933)
                                      └─ local embedder (multilingual-e5-large on MPS)
```

- MCPサーバーはstdio transport
- OpenVikingサーバーが別プロセスで常駐（`localhost:1933`）
- MCPサーバーは `httpx` でHTTP APIを叩く薄いプロキシ

## 置き場所

```
06_code/openviking-mcp/
├── server.py          # MCPサーバー本体
├── requirements.txt   # mcp, httpx
├── docs/              # 設計書（このファイル）
└── research/          # 調査ログ（既存）
```

## Tools（7つ）

### viking_find — セマンティック検索

```
POST /api/v1/search/find
```

- 入力: `query` (str), `top_k` (int, default=5)
- 出力: リソース/メモリのリスト（各エントリにL0 abstract含む）
- description: "セマンティック検索。結果にはL0要約が含まれる。L0で十分な情報があればそのまま使い、もう少し構造を知りたい場合のみviking_overviewでL1を取得し、全文が必要な場合のみviking_readでL2を取得すること。"

### viking_read — L2フルコンテンツ

```
GET /api/v1/content/read?uri=...
```

- 入力: `uri` (str)
- 出力: 全文テキスト
- description: "URIの全文（L2）を取得する。トークンを多く消費するため、viking_findのL0やviking_overviewのL1で情報が不足する場合のみ使用すること。"

### viking_ls — ディレクトリ一覧

```
GET /api/v1/fs/ls?uri=...
```

- 入力: `uri` (str, default="viking://resources/")
- 出力: ファイル/ディレクトリ一覧（各エントリにabstract含む）

### viking_add — リソース追加

```
POST /api/v1/resources
```

- 入力: `path` (str) — ローカルファイルパス
- 出力: 追加結果（root_uri）

### viking_abstract — L0要約

```
GET /api/v1/content/abstract?uri=...
```

- 入力: `uri` (str)
- 出力: 1-2文の要約（約100トークン）
- description: "URIのL0要約を取得する。最小コストで内容を把握できる。"

### viking_overview — L1概要

```
GET /api/v1/content/overview?uri=...
```

- 入力: `uri` (str)
- 出力: 構造化された概要（約2kトークン）
- description: "URIのL1概要を取得する。L0より詳しいがL2より軽量。セクション構成や要点を把握したい場合に使う。"

### viking_grep — テキスト検索

```
POST /api/v1/search/grep
```

- 入力: `pattern` (str), `uri` (str, optional)
- 出力: マッチ結果リスト

## 段階的ロードフロー

```
1. viking_find("古賀凛のGhost") → L0要約付きリスト
   └─ "キャラ設計の古賀Ghost形成過程" (score: 0.50)

2. L0で「場所は分かったけど詳細が欲しい」と判断
   └─ viking_overview("viking://resources/characters/koga-rin") → L1概要

3. L1で「Ghost形成の具体的な記述が必要」と判断
   └─ viking_read("viking://resources/characters/koga-rin/ghost.md") → L2全文
```

## Claude Code settings.json 設定

```json
{
  "mcpServers": {
    "openviking": {
      "command": "/Users/yoshida/.anyenv/envs/pyenv/versions/3.10.7/bin/python",
      "args": ["/Users/yoshida/src/work/ai-management/06_code/openviking-mcp/server.py"],
      "env": {
        "OPENVIKING_URL": "http://127.0.0.1:1933"
      }
    }
  }
}
```

## 前提条件

- OpenVikingサーバーが `localhost:1933` で起動済み
- local embedding provider が設定済み（`ov.conf` に `provider: "local"`）

## 依存

- `mcp` — MCP Python SDK
- `httpx` — async HTTP client

## エラーハンドリング

- OpenVikingサーバー未起動時: tool呼び出しで「OpenViking server is not running at {url}」を返す
- 不正URI: OpenVikingのエラーレスポンスをそのまま返す
