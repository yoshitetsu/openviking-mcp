# OpenViking Embedder実装 調査レポート

調査日: 2026-03-22
対象バージョン: インストール済みパッケージ（site-packages）

---

## 1. DenseEmbedderBase クラスの定義

### ファイルパス
```
openviking/models/embedder/base.py
```

### クラス継承階層
```
EmbedderBase (ABC)              # 全embedderの最上位基底クラス
├── DenseEmbedderBase           # Dense embedder基底
├── SparseEmbedderBase          # Sparse embedder基底
├── HybridEmbedderBase          # Hybrid embedder基底
│   └── CompositeHybridEmbedder # Dense+Sparseの合成
```

### EmbedderBase インターフェース
```python
class EmbedderBase(ABC):
    def __init__(self, model_name: str, config: Optional[Dict[str, Any]] = None)

    @abstractmethod
    def embed(self, text: str, is_query: bool = False) -> EmbedResult  # 必須override

    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[EmbedResult]  # デフォルト実装あり（ループ）

    def close(self)  # リソース解放用、デフォルト空

    @property
    def is_dense(self) -> bool   # デフォルト True
    @property
    def is_sparse(self) -> bool  # デフォルト False
    @property
    def is_hybrid(self) -> bool  # デフォルト False
```

### DenseEmbedderBase インターフェース
```python
class DenseEmbedderBase(EmbedderBase):
    @abstractmethod
    def embed(self, text: str, is_query: bool = False) -> EmbedResult

    @abstractmethod
    def get_dimension(self) -> int
```

### EmbedResult データクラス
```python
@dataclass
class EmbedResult:
    dense_vector: Optional[List[float]] = None
    sparse_vector: Optional[Dict[str, float]] = None

    # プロパティ: is_dense, is_sparse, is_hybrid
```

---

## 2. 既存embedder実装一覧

### ファイルパスと対応プロバイダー

| ファイル | クラス名 | プロバイダー | タイプ |
|---------|---------|------------|--------|
| `openai_embedders.py` | `OpenAIDenseEmbedder` | openai | Dense |
| `openai_embedders.py` | `OpenAISparseEmbedder` | - | (NotImplemented) |
| `openai_embedders.py` | `OpenAIHybridEmbedder` | - | (NotImplemented) |
| `voyage_embedders.py` | `VoyageDenseEmbedder` | voyage | Dense |
| `jina_embedders.py` | `JinaDenseEmbedder` | jina | Dense |
| `volcengine_embedders.py` | `VolcengineDenseEmbedder` | volcengine | Dense |
| `volcengine_embedders.py` | `VolcengineSparseEmbedder` | volcengine | Sparse |
| `volcengine_embedders.py` | `VolcengineHybridEmbedder` | volcengine | Hybrid |
| `vikingdb_embedders.py` | `VikingDBDenseEmbedder` | vikingdb | Dense |
| `vikingdb_embedders.py` | `VikingDBSparseEmbedder` | vikingdb | Sparse |
| `vikingdb_embedders.py` | `VikingDBHybridEmbedder` | vikingdb | Hybrid |

### 共通実装パターン（OpenAI/Voyage/Jinaの場合）

全てOpenAI互換APIクライアントを使用：
```python
class XxxDenseEmbedder(DenseEmbedderBase):
    def __init__(self, model_name, api_key, api_base, dimension, ...):
        super().__init__(model_name, config)
        self.client = openai.OpenAI(api_key=api_key, base_url=api_base)
        self._dimension = dimension or DEFAULT_DIM

    def embed(self, text, is_query=False) -> EmbedResult:
        response = self.client.embeddings.create(input=text, model=self.model_name)
        vector = response.data[0].embedding
        return EmbedResult(dense_vector=vector)

    def embed_batch(self, texts, is_query=False) -> List[EmbedResult]:
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        return [EmbedResult(dense_vector=item.embedding) for item in response.data]

    def get_dimension(self) -> int:
        return self._dimension
```

### 非対称embedding（query/document区別）

- **OpenAI**: `query_param` / `document_param` で `extra_body` に `input_type` を渡す
- **Jina**: `query_param` / `document_param` で `extra_body` に `task` を渡す（デフォルト: `retrieval.query` / `retrieval.passage`）
- **Voyage**: 非対称未対応（`is_query` は無視される）

---

## 3. sentence-transformersでカスタムembedderを作る最小実装

### 必須overrideメソッド（2つだけ）

```python
from typing import Any, Dict, List, Optional
from openviking.models.embedder.base import DenseEmbedderBase, EmbedResult


class SentenceTransformerEmbedder(DenseEmbedderBase):
    """sentence-transformersベースのカスタムembedder"""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        dimension: Optional[int] = None,
        device: str = "cpu",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_name, config)
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)
        self._dimension = dimension or self.model.get_sentence_embedding_dimension()

    def embed(self, text: str, is_query: bool = False) -> EmbedResult:
        """【必須】単一テキストのembedding"""
        # E5系モデルの場合、query/passageプレフィックスをつける
        if is_query:
            text = f"query: {text}"
        else:
            text = f"passage: {text}"

        vector = self.model.encode(text, normalize_embeddings=True).tolist()

        if self._dimension and len(vector) > self._dimension:
            vector = vector[:self._dimension]

        return EmbedResult(dense_vector=vector)

    def get_dimension(self) -> int:
        """【必須】ベクトル次元数を返す"""
        return self._dimension

    # --- 以下はオプション（パフォーマンス最適化） ---

    def embed_batch(self, texts: List[str], is_query: bool = False) -> List[EmbedResult]:
        """【任意】バッチ処理の最適化（デフォルトはループ）"""
        prefixed = [
            f"{'query' if is_query else 'passage'}: {t}" for t in texts
        ]
        vectors = self.model.encode(prefixed, normalize_embeddings=True, batch_size=32)
        return [EmbedResult(dense_vector=v.tolist()) for v in vectors]

    def close(self):
        """【任意】リソース解放"""
        del self.model
```

### overrideまとめ

| メソッド | 必須？ | 説明 |
|---------|-------|------|
| `embed(text, is_query)` | **必須** | 単一テキスト → `EmbedResult` |
| `get_dimension()` | **必須** | ベクトル次元数を返す |
| `embed_batch(texts, is_query)` | 任意 | バッチ最適化（デフォルトはembed()のループ） |
| `close()` | 任意 | リソース解放 |

---

## 4. 設定ファイル（ov.conf）でembedderを切り替える方法

### 設定ファイルの場所

優先順位:
1. `--config` オプション（CLIの場合）
2. 環境変数 `OPENVIKING_CONFIG_FILE`
3. `~/.openviking/ov.conf`（デフォルト）

### ov.confのフォーマット（JSON）

```json
{
  "embedding": {
    "dense": {
      "provider": "openai",
      "model": "text-embedding-3-large",
      "api_key": "sk-xxx",
      "api_base": "https://api.openai.com/v1",
      "dimension": 3072
    }
  }
}
```

### 対応providerとパラメータ

#### provider: "openai"（OpenAI互換API全般）
```json
{
  "provider": "openai",
  "model": "text-embedding-3-small",
  "api_key": "sk-xxx",
  "api_base": "https://api.openai.com/v1",
  "dimension": 1536,
  "query_param": null,
  "document_param": null,
  "extra_headers": {}
}
```

#### provider: "ollama"（ローカル実行）
```json
{
  "provider": "ollama",
  "model": "nomic-embed-text",
  "api_base": "http://localhost:11434/v1",
  "dimension": 768
}
```
※ 内部的には `OpenAIDenseEmbedder` が使われる（api_key不要）

#### provider: "voyage"
```json
{
  "provider": "voyage",
  "model": "voyage-4-lite",
  "api_key": "pa-xxx",
  "dimension": 1024
}
```

#### provider: "jina"
```json
{
  "provider": "jina",
  "model": "jina-embeddings-v5-text-small",
  "api_key": "jina_xxx",
  "dimension": 512,
  "query_param": "retrieval.query",
  "document_param": "retrieval.passage"
}
```

#### provider: "volcengine"
```json
{
  "provider": "volcengine",
  "model": "doubao-embedding",
  "api_key": "xxx",
  "dimension": 2048,
  "input": "multimodal"
}
```

#### provider: "vikingdb"
```json
{
  "provider": "vikingdb",
  "model": "xxx",
  "ak": "access-key",
  "sk": "secret-key",
  "region": "cn-beijing",
  "version": "1.0"
}
```

### ハイブリッド検索の設定例

```json
{
  "embedding": {
    "dense": {
      "provider": "openai",
      "model": "text-embedding-3-large",
      "api_key": "sk-xxx",
      "dimension": 3072
    },
    "sparse": {
      "provider": "volcengine",
      "model": "doubao-embedding",
      "api_key": "xxx"
    }
  }
}
```

または単一モデルでhybrid:
```json
{
  "embedding": {
    "hybrid": {
      "provider": "volcengine",
      "model": "doubao-embedding",
      "api_key": "xxx"
    }
  }
}
```

### 設定のロードフロー

```
ov.conf → load_json_config() → EmbeddingConfig (Pydantic)
    → EmbeddingConfig.get_embedder()
        → _create_embedder(provider, type, config)  # ファクトリーレジストリで分岐
```

ファクトリーレジストリ（`embedding_config.py`内）が `(provider, type)` タプルで対応クラスとパラメータビルダーをマッピングしている。

### カスタムembedderを登録する場合の課題

**現状、ov.confのproviderフィールドはハードコードのバリデーション:**
```python
if self.provider not in ["openai", "volcengine", "vikingdb", "jina", "ollama", "voyage"]:
    raise ValueError(...)
```

sentence-transformersなどカスタムproviderを追加するには:
1. `EmbeddingModelConfig.validate_config()` のproviderリストに追加
2. `EmbeddingConfig._create_embedder()` のfactory_registryにエントリ追加
3. **または**、`provider: "openai"` + `api_base: "http://localhost:PORT/v1"` でOpenAI互換サーバー（TEIなど）経由で使う（パッケージ変更不要）

---

## 補足: 関連ファイルパス一覧

```
# embedder本体
openviking/models/embedder/__init__.py
openviking/models/embedder/base.py
openviking/models/embedder/openai_embedders.py
openviking/models/embedder/voyage_embedders.py
openviking/models/embedder/jina_embedders.py
openviking/models/embedder/volcengine_embedders.py
openviking/models/embedder/vikingdb_embedders.py

# 設定システム
openviking_cli/utils/config/embedding_config.py   ← EmbeddingConfig, ファクトリーレジストリ
openviking_cli/utils/config/consts.py              ← デフォルトパス定義
openviking_cli/utils/config/open_viking_config.py  ← 統合設定ローダー
openviking/server/config.py                        ← サーバー設定

# 実際の設定ファイル
~/.openviking/ov.conf
```
