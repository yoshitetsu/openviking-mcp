# ローカルEmbeddingライブラリ調査 (2026年3月時点)

## 1. sentence-transformersの現在の位置づけ

### 基本情報
- **GitHub Stars:** 18.4k / Forks: 2.8k
- **PyPI月間DL数:** 約1,710万 (17.1M/月)
- **依存プロジェクト数:** 126,000+
- **最新バージョン:** v5.3.0 (2026-03-12)
- **メンテナ:** Tom Aarsen (HuggingFace所属)
- **要件:** Python 3.10+, PyTorch 1.11.0+, transformers v4.34.0+

### 主要ユースケース
- セマンティック検索、テキスト類似度計算、クラスタリング、パラフレーズ検出
- HuggingFace上に15,000+の事前学習済みモデル
- 100+言語のマルチリンガル対応
- 20+のロス関数によるファインチューニング

### 結論
**2026年3月時点でもデファクトスタンダード。** 月間1,700万DL、12.6万の依存プロジェクトという規模は他の追随を許さない。ただし「ローカル軽量推論」に限定すると、PyTorch依存の重さがネックとなり、用途次第では競合が優位になるケースがある。

---

## 2. 競合・代替ライブラリ一覧

| ライブラリ | Stars | 主な用途 | バックエンド | 依存の重さ |
|-----------|-------|---------|------------|-----------|
| **sentence-transformers** | 18.4k | 汎用embedding＋学習 | PyTorch | 重い (PyTorch必須) |
| **FastEmbed** (Qdrant) | 2.8k | 軽量ローカル推論 | ONNX Runtime | 軽い |
| **HuggingFace TEI** | 4.6k | 本番サービング | Candle/Flash Attention | Docker前提 |
| **llama.cpp** (embedding) | 80k+ | GGUF形式のモデル推論 | C++ (GGML) | 軽い |
| **Ollama** (embedding) | 120k+ | ワンコマンドローカルLLM | llama.cpp | 中程度 (バイナリ配布) |
| **ONNX Runtime直接** | — | カスタム推論パイプライン | ONNX | 軽い |
| **OpenVINO** | — | Intel CPU最適化 | OpenVINO | 中程度 |

---

## 3. 各ライブラリの強み・弱み

### sentence-transformers
| 強み | 弱み |
|-----|-----|
| 最大のエコシステム・モデル数 | PyTorch依存でインストールが重い (数GB) |
| 学習・ファインチューニングが容易 | CPU推論はFastEmbedより遅い場合がある |
| ドキュメント・コミュニティが充実 | サーバーレス環境には不向き |
| ONNX/OpenVINOバックエンドも選択可 | GPU前提の設計思想 |
| v5.3でStatic Embeddingサポート (400倍高速) | — |

### FastEmbed (Qdrant)
| 強み | 弱み |
|-----|-----|
| ONNX Runtimeベースで軽量 (PyTorch不要) | モデル選択肢がsentence-transformersより少ない |
| GPUなしでも実用的な速度 | Apple Silicon (M2等)で遅いとの報告あり |
| Sparse (SPLADE)・Late interaction (ColBERT)対応 | ファインチューニング非対応 |
| サーバーレス環境に最適 | Qdrantエコシステムへの暗黙の誘導 |
| pip一発で軽量インストール | v0.7.4 — まだv1未満 |

### HuggingFace TEI (Text Embeddings Inference)
| 強み | 弱み |
|-----|-----|
| Token-based dynamic batchingで高スループット | Dockerコンテナ前提の運用 |
| Flash Attention最適化 | Pythonライブラリとしては使えない |
| 本番メトリクス (Prometheus/OpenTelemetry) | GPUがないと性能メリットが薄い |
| Metal対応でMacローカルも可 | 設定・運用の学習コストが高い |

### llama.cpp (embedding mode)
| 強み | 弱み |
|-----|-----|
| GGUF量子化モデルでメモリ効率が極めて高い | 対応embeddingモデルが限定的 |
| C++実装で高速 | HTTPサーバー経由の利用が前提 |
| GPU/CPUどちらでも動作 | Python APIは間接的 (llama-cpp-python) |
| Ollamaの内部エンジンでもある | embedding専用ツールとしてはオーバースペック |

### Ollama (embedding endpoint)
| 強み | 弱み |
|-----|-----|
| ワンコマンドセットアップ | バッチ処理が非効率 (1リクエスト=1文字列) |
| nomic-embed-text等の人気モデルがpull一発 | asyncio.gatherで並列化が必要 |
| REST API / Python SDK両対応 | 大量テキストのembeddingには不向き |
| LLMとembeddingを同一基盤で管理 | カスタムモデルの投入が面倒 |

---

## 4. 2026年時点のベストプラクティス

### 用途別推奨

| ユースケース | 推奨 | 理由 |
|-------------|------|------|
| **RAGプロトタイプ/研究** | sentence-transformers | モデル選択肢が最多、学習もできる |
| **軽量ローカル (PyTorch避けたい)** | FastEmbed | ONNX Runtimeのみ、pip install一発 |
| **本番サービング (GPU有)** | HuggingFace TEI | バッチング・メトリクス・最適化 |
| **既にOllamaでLLM運用中** | Ollama embed | 追加インストール不要 |
| **メモリ制約が厳しい** | llama.cpp + GGUF | 量子化で最小フットプリント |
| **超高速CPU推論** | sentence-transformers Static Embedding | 400倍速、distillation前提 |

### 推奨モデル (2026年3月時点)

| モデル | パラメータ | 次元 | 特徴 |
|--------|-----------|------|------|
| nomic-embed-text-v1.5 | 137M | 768 | 軽量・汎用・Ollama/FastEmbed対応 |
| mxbai-embed-large | 335M | 1024 | 高精度・英語特化 |
| Qwen3-Embedding-0.6B | 600M | 可変 | 多言語・最新 |
| EmbeddingGemma-300M | 300M | — | Google製・オンデバイス最適化 |
| multilingual-e5-large | 560M | 1024 | 多言語ベンチマーク上位 |

### このMCPプロジェクト (OpenViking) への示唆

ローカルembeddingを組み込む場合の現実的な選択肢:

1. **FastEmbed** — PyTorch不要で依存が軽い。MCPサーバーのようなツール組み込みには最適。ONNX Runtime単体で動くため、デプロイサイズが小さい
2. **sentence-transformers (ONNX backend)** — v5.3ではONNXバックエンドも公式サポート。モデル互換性を重視するならこちら
3. **Ollama embed** — ユーザーが既にOllamaを使っている前提なら、追加依存ゼロ

**判断基準:** 「依存の軽さ」と「モデル選択の自由度」のトレードオフ。MCPサーバーとして配布するなら、FastEmbedの軽量さが有利。研究・実験フェーズならsentence-transformersの柔軟性が有利。

---

## 調査ソース

- [sentence-transformers GitHub](https://github.com/UKPLab/sentence-transformers) — 18.4k stars
- [sentence-transformers PyPI Stats](https://pypistats.org/packages/sentence-transformers) — 月間17.1M DL
- [FastEmbed GitHub](https://github.com/qdrant/fastembed) — 2.8k stars
- [HuggingFace TEI GitHub](https://github.com/huggingface/text-embeddings-inference) — 4.6k stars
- [llama.cpp GitHub](https://github.com/ggml-org/llama.cpp) — 80k+ stars
- [Ollama Embeddings Docs](https://docs.ollama.com/capabilities/embeddings)
- [Best Open-Source Embedding Models 2026 (BentoML)](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models)
- [Embedding Models Comparison 2026 (Elephas)](https://elephas.app/blog/best-embedding-models)
- [Haystack: Choosing the Right Embedder](https://docs.haystack.deepset.ai/docs/choosing-the-right-embedder)
- [FastEmbed vs Sentence Transformers (NewMind AI)](https://newmind.ai/en/blog/comparing-fastembed-and-sentence-transformers-a-comprehensive-guide-to-text-embedding-libraries)
- [Static Embeddings Blog (HuggingFace)](https://huggingface.co/blog/static-embeddings)
