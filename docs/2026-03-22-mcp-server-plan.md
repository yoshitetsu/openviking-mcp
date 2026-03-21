# OpenViking MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Claude CodeからOpenVikingのコンテキストDBにMCP経由でアクセスし、L0/L1/L2の段階的ロードでトークンを節約する。

**Architecture:** FastMCP (stdio transport) + httpx async clientでOpenViking HTTP APIをラップする薄いプロキシ。1ファイル完結。

**Tech Stack:** mcp (FastMCP), httpx, Python 3.10+

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `06_code/openviking-mcp/server.py` | MCPサーバー本体（7 tools） |
| Create | `06_code/openviking-mcp/requirements.txt` | 依存パッケージ |

---

### Task 1: MCPサーバー実装

- [ ] server.py — 7 tools全部実装
- [ ] requirements.txt
- [ ] 動作確認（mcp dev or claude code）

### Task 2: settings.json登録 + E2Eテスト

- [ ] settings.jsonにMCPサーバー登録
- [ ] Claude Codeから実際にtool呼び出し確認
