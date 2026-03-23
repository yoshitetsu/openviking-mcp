#!/usr/bin/env python3
"""L0/L1/L2の段階的ロードによるトークン節約効果を計測する。

前提: OpenVikingサーバーが localhost:1933 で起動済み。
      天才の壊し方の設計書6ファイルがリソースとして登録済み。
"""

import httpx
import json
import tiktoken

BASE_URL = "http://127.0.0.1:1933"
enc = tiktoken.encoding_for_model("gpt-4o")


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def get(path: str, params: dict = None) -> dict:
    resp = httpx.get(f"{BASE_URL}/api/v1{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{BASE_URL}/api/v1{path}", json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    print("=" * 60)
    print("OpenViking L0/L1/L2 トークン節約効果の計測")
    print("=" * 60)

    # --- リソース一覧取得 ---
    ls_data = get("/fs/ls", {"uri": "viking://resources/"})
    resources = ls_data.get("result", [])
    print(f"\n登録リソース数: {len(resources)}")

    # --- 全リソースのURIを収集 ---
    all_uris = []
    for res in resources:
        uri = res.get("uri", "")
        is_dir = res.get("isDir", False)
        if is_dir:
            # サブディレクトリ内のファイルも取得
            sub = get("/fs/ls", {"uri": uri})
            for item in sub.get("result", []):
                if not item.get("isDir", False):
                    all_uris.append(item["uri"])
        else:
            all_uris.append(uri)

    print(f"全ファイル数: {len(all_uris)}")

    # ================================================================
    # 計測1: L2全文読み（従来方式 = 全部コンテキストに載せる）
    # ================================================================
    print("\n--- 計測1: L2 全文読み（従来方式）---")
    total_l2_tokens = 0
    l2_details = []
    for uri in all_uris:
        try:
            data = get("/content/read", {"uri": uri})
            content = data.get("result", "")
            tokens = count_tokens(content)
            total_l2_tokens += tokens
            short_uri = uri.split("resources/")[-1] if "resources/" in uri else uri
            l2_details.append((short_uri, tokens, len(content)))
        except Exception as e:
            print(f"  [skip] {uri}: {e}")

    for uri, tokens, chars in sorted(l2_details, key=lambda x: -x[1]):
        print(f"  {uri:50s} {tokens:>6,} tok ({chars:>6,} chars)")
    print(f"  {'合計':50s} {total_l2_tokens:>6,} tok")

    # ================================================================
    # 計測2: L0のみ（viking_find のabstract）
    # ================================================================
    print("\n--- 計測2: L0 要約のみ ---")
    total_l0_tokens = 0
    l0_details = []

    # ls結果のabstractを使う（find結果と同等）
    for res in resources:
        abstract = res.get("abstract", "")
        if abstract:
            tokens = count_tokens(abstract)
            total_l0_tokens += tokens
            short_uri = res["uri"].split("resources/")[-1]
            l0_details.append((short_uri, tokens))

    for uri, tokens in l0_details:
        print(f"  {uri:50s} {tokens:>6,} tok")
    print(f"  {'合計':50s} {total_l0_tokens:>6,} tok")

    # ================================================================
    # 計測3: L0 + L1（overviewを取得）
    # ================================================================
    print("\n--- 計測3: L0 + L1 概要 ---")
    total_l1_tokens = total_l0_tokens  # L0は既にカウント済み
    l1_details = []
    for res in resources:
        uri = res.get("uri", "")
        try:
            data = get("/content/overview", {"uri": uri})
            overview = data.get("result", "")
            if overview:
                tokens = count_tokens(overview)
                total_l1_tokens += tokens
                short_uri = uri.split("resources/")[-1]
                l1_details.append((short_uri, tokens))
        except Exception:
            pass

    for uri, tokens in l1_details:
        print(f"  L1 {uri:47s} {tokens:>6,} tok")
    print(f"  {'L0 + L1 合計':50s} {total_l1_tokens:>6,} tok")

    # ================================================================
    # 計測4: セマンティック検索結果
    # ================================================================
    print("\n--- 計測4: viking_find クエリ結果 ---")
    queries = [
        "古賀凛のキャラクター設計",
        "真壁陽の動機とAGIとの関係",
        "藤堂の死の設計",
    ]
    for q in queries:
        try:
            data = post("/search/find", {"query": q, "top_k": 3})
            result = data.get("result", {})
            all_items = result.get("memories", []) + result.get("resources", [])
            find_text = ""
            for item in all_items[:3]:
                find_text += f"{item.get('uri', '')} (score: {item.get('score', 0):.3f})\n"
                find_text += f"{item.get('abstract', '')}\n\n"
            tokens = count_tokens(find_text)
            print(f"  query: \"{q}\"")
            print(f"    top-3 結果: {tokens:,} tok")
        except Exception as e:
            print(f"  query: \"{q}\" → error: {e}")

    # ================================================================
    # サマリ
    # ================================================================
    print("\n" + "=" * 60)
    print("サマリ")
    print("=" * 60)
    print(f"  L2 全文読み（従来）:  {total_l2_tokens:>8,} tok")
    print(f"  L0 要約のみ:          {total_l0_tokens:>8,} tok  ({100 - total_l0_tokens/max(total_l2_tokens,1)*100:.0f}% 削減)")
    print(f"  L0 + L1:              {total_l1_tokens:>8,} tok  ({100 - total_l1_tokens/max(total_l2_tokens,1)*100:.0f}% 削減)")
    print(f"  L0 + L1 + L2(1件):    {total_l1_tokens + (l2_details[0][1] if l2_details else 0):>8,} tok  (最大1件のみ全文)")


if __name__ == "__main__":
    main()
