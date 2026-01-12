"""
Integration tests for VoyageAI embeddings and reranker.

These tests require a valid VOYAGE_API_KEY environment variable.
Run with: VOYAGE_API_KEY=your_key pytest tests/embeddings/test_voyageai_integration.py -v
"""

import os

import pytest

# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    not os.getenv("VOYAGE_API_KEY"),
    reason="VOYAGE_API_KEY environment variable not set",
)


class TestVoyageAIEmbeddingsIntegration:
    """Integration tests for VoyageAI embeddings."""

    @pytest.fixture
    def embedder(self):
        """Create a VoyageAI embedder instance."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3.5")
        return VoyageAIEmbedding(config)

    def test_embed_single_text(self, embedder):
        """Test embedding a single text."""
        result = embedder.embed("Hello, world!")

        assert isinstance(result, list)
        assert len(result) == 1024  # Default dimension
        assert all(isinstance(x, float) for x in result)

    def test_embed_with_memory_action_add(self, embedder):
        """Test embedding with 'add' memory action (document type)."""
        result = embedder.embed("This is a document to store.", memory_action="add")

        assert isinstance(result, list)
        assert len(result) == 1024

    def test_embed_with_memory_action_search(self, embedder):
        """Test embedding with 'search' memory action (query type)."""
        result = embedder.embed("What is the meaning of life?", memory_action="search")

        assert isinstance(result, list)
        assert len(result) == 1024

    def test_embed_batch(self, embedder):
        """Test batch embedding multiple texts."""
        texts = [
            "First document about Python programming.",
            "Second document about machine learning.",
            "Third document about artificial intelligence.",
        ]
        result = embedder.embed_batch(texts, memory_action="add")

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(emb) == 1024 for emb in result)

    def test_embed_batch_empty(self, embedder):
        """Test batch embedding with empty list."""
        result = embedder.embed_batch([])
        assert result == []

    def test_embed_with_custom_dimensions(self):
        """Test embedding with custom output dimensions."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=512)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test with custom dimensions")

        assert len(result) == 512

    def test_embed_asymmetric_query_document(self, embedder):
        """Test that query and document embeddings are different (asymmetric)."""
        text = "What is machine learning?"

        query_embedding = embedder.embed(text, memory_action="search")
        doc_embedding = embedder.embed(text, memory_action="add")

        # Query and document embeddings should be different
        assert query_embedding != doc_embedding

    def test_embed_similarity(self, embedder):
        """Test that similar texts have similar embeddings."""
        import math

        def cosine_similarity(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b)

        emb1 = embedder.embed("The cat sat on the mat.", memory_action="add")
        emb2 = embedder.embed("A cat was sitting on a mat.", memory_action="add")
        emb3 = embedder.embed("Quantum physics explains particle behavior.", memory_action="add")

        sim_similar = cosine_similarity(emb1, emb2)
        sim_different = cosine_similarity(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_similar > sim_different
        assert sim_similar > 0.8  # Similar texts should be highly correlated


class TestVoyageAIContextualizedEmbeddingsIntegration:
    """Integration tests for VoyageAI contextualized embeddings."""

    @pytest.fixture
    def embedder(self):
        """Create a VoyageAI embedder for contextualized embeddings."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(
            model="voyage-3.5",  # Base model for single embeds
            voyageai_context_model="voyage-context-3",
        )
        return VoyageAIEmbedding(config)

    def test_embed_contextualized_single_document(self, embedder):
        """Test contextualized embedding for a single document."""
        chunks = [
            ["Introduction to AI", "Machine learning basics", "Deep learning overview"]
        ]
        result = embedder.embed_contextualized(chunks, memory_action="add")

        assert isinstance(result, list)
        assert len(result) == 3  # One embedding per chunk
        assert all(len(emb) == 1024 for emb in result)

    def test_embed_contextualized_multiple_documents(self, embedder):
        """Test contextualized embedding for multiple documents."""
        chunks = [
            ["Doc 1 intro", "Doc 1 body"],
            ["Doc 2 intro", "Doc 2 body", "Doc 2 conclusion"],
        ]
        result = embedder.embed_contextualized(chunks, memory_action="add")

        assert len(result) == 5  # 2 + 3 chunks total


class TestVoyageAIRerankerIntegration:
    """Integration tests for VoyageAI reranker."""

    @pytest.fixture
    def reranker(self):
        """Create a VoyageAI reranker instance."""
        from mem0.configs.rerankers.voyageai import VoyageAIRerankerConfig
        from mem0.reranker.voyageai_reranker import VoyageAIReranker

        config = VoyageAIRerankerConfig(model="rerank-2")
        return VoyageAIReranker(config)

    def test_rerank_basic(self, reranker):
        """Test basic reranking functionality."""
        query = "What is machine learning?"
        documents = [
            {"memory": "Python is a programming language."},
            {"memory": "Machine learning is a subset of artificial intelligence."},
            {"memory": "The weather is nice today."},
        ]

        result = reranker.rerank(query, documents)

        assert len(result) == 3
        assert all("rerank_score" in doc for doc in result)
        # ML document should rank highest
        assert "machine learning" in result[0]["memory"].lower()

    def test_rerank_with_top_k(self, reranker):
        """Test reranking with top_k limit."""
        query = "artificial intelligence"
        documents = [
            {"memory": "AI is transforming industries."},
            {"memory": "Cooking recipes for beginners."},
            {"memory": "Deep learning neural networks."},
            {"memory": "Garden maintenance tips."},
        ]

        result = reranker.rerank(query, documents, top_k=2)

        assert len(result) == 2
        # Both returned docs should be AI-related
        for doc in result:
            assert doc["rerank_score"] > 0

    def test_rerank_preserves_metadata(self, reranker):
        """Test that reranking preserves document metadata."""
        query = "test query"
        documents = [
            {"memory": "Document content", "id": "doc1", "metadata": {"source": "test"}},
        ]

        result = reranker.rerank(query, documents)

        assert result[0]["id"] == "doc1"
        assert result[0]["metadata"] == {"source": "test"}
        assert "rerank_score" in result[0]

    def test_rerank_empty_documents(self, reranker):
        """Test reranking with empty document list."""
        result = reranker.rerank("query", [])
        assert result == []

    def test_rerank_score_ordering(self, reranker):
        """Test that results are ordered by relevance score."""
        query = "Python programming"
        documents = [
            {"memory": "Java is a popular programming language."},
            {"memory": "Python is great for data science and machine learning."},
            {"memory": "The python snake is a large reptile."},
        ]

        result = reranker.rerank(query, documents)

        # Check scores are in descending order
        scores = [doc["rerank_score"] for doc in result]
        assert scores == sorted(scores, reverse=True)


class TestVoyageAIDimensionsAndDtypeIntegration:
    """Integration tests for different output dimensions and data types."""

    def test_voyage_3_large_dimensions_256(self):
        """Test voyage-3-large with 256 dimensions."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=256)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test 256 dimensions")
        assert len(result) == 256

    def test_voyage_3_large_dimensions_512(self):
        """Test voyage-3-large with 512 dimensions."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=512)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test 512 dimensions")
        assert len(result) == 512

    def test_voyage_3_large_dimensions_1024(self):
        """Test voyage-3-large with 1024 dimensions (default)."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=1024)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test 1024 dimensions")
        assert len(result) == 1024

    def test_voyage_3_large_dimensions_2048(self):
        """Test voyage-3-large with 2048 dimensions."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=2048)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test 2048 dimensions")
        assert len(result) == 2048

    def test_output_dtype_float(self):
        """Test float output dtype (default)."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", voyageai_output_dtype="float")
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test float dtype")
        assert all(isinstance(x, float) for x in result)

    def test_output_dtype_int8(self):
        """Test int8 quantized output."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", voyageai_output_dtype="int8")
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test int8 dtype")
        # int8 values should be in range [-128, 127]
        assert all(-128 <= x <= 127 for x in result)

    def test_output_dtype_ubinary(self):
        """Test unsigned binary quantized output."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large", voyageai_output_dtype="ubinary")
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Test ubinary dtype")
        # ubinary packs bits into bytes, so output length is dims/8
        assert len(result) == 1024 // 8  # 128 bytes for 1024 dims


class TestVoyageAIModelTypesIntegration:
    """Integration tests for different VoyageAI model types."""

    def test_voyage_3_5_text_model(self):
        """Test voyage-3.5 text model (recommended default)."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3.5")
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Standard text embedding test")
        assert len(result) == 1024

    def test_voyage_3_large_text_model(self):
        """Test voyage-3-large text model."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3-large")
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Large model text embedding test")
        assert len(result) == 1024

    def test_voyage_3_lite_text_model(self):
        """Test voyage-3-lite text model (faster, cheaper)."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        # voyage-3-lite only supports 512 dimensions
        config = BaseEmbedderConfig(model="voyage-3-lite", embedding_dims=512)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Lite model text embedding test")
        assert len(result) == 512

    def test_voyage_3_5_lite_text_model(self):
        """Test voyage-3.5-lite text model with flexible dimensions."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        # voyage-3.5-lite supports 256, 512, 1024 (default), 2048 dimensions
        config = BaseEmbedderConfig(model="voyage-3.5-lite", embedding_dims=1024)
        embedder = VoyageAIEmbedding(config)

        result = embedder.embed("Lite 3.5 model text embedding test")
        assert len(result) == 1024

    def test_voyage_3_5_lite_custom_dimensions(self):
        """Test voyage-3.5-lite with various dimension options."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        for dims in [256, 512, 2048]:
            config = BaseEmbedderConfig(model="voyage-3.5-lite", embedding_dims=dims)
            embedder = VoyageAIEmbedding(config)
            result = embedder.embed(f"Test {dims} dims")
            assert len(result) == dims, f"Expected {dims} dims, got {len(result)}"

    def test_voyage_code_3_model(self):
        """Test voyage-code-3 model for code embeddings."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-code-3")
        embedder = VoyageAIEmbedding(config)

        code_snippet = "def hello_world():\n    print('Hello, World!')"
        result = embedder.embed(code_snippet)
        assert len(result) == 1024

    def test_voyage_context_3_model(self):
        """Test voyage-context-3 for contextualized embeddings."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(voyageai_context_model="voyage-context-3")
        embedder = VoyageAIEmbedding(config)

        chunks = [["Chapter 1: Introduction", "Chapter 2: Methods", "Chapter 3: Results"]]
        result = embedder.embed_contextualized(chunks)

        assert len(result) == 3
        assert all(len(emb) == 1024 for emb in result)

    def test_voyage_multimodal_3_model(self):
        """Test voyage-multimodal-3.5 with text-only input."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(voyageai_multimodal_model="voyage-multimodal-3.5")
        embedder = VoyageAIEmbedding(config)

        # Multimodal model can also handle text-only input
        result = embedder.embed_multimodal(["A beautiful sunset over the ocean"])
        assert len(result) == 1024

    def test_voyage_multimodal_with_image(self):
        """Test voyage-multimodal-3.5 with actual image."""
        from PIL import Image

        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(voyageai_multimodal_model="voyage-multimodal-3.5")
        embedder = VoyageAIEmbedding(config)

        # Create a simple test image
        img = Image.new("RGB", (100, 100), color="red")

        result = embedder.embed_multimodal(["A red square image", img])
        assert len(result) == 1024

    def test_rerank_2_model(self):
        """Test rerank-2 model."""
        from mem0.configs.rerankers.voyageai import VoyageAIRerankerConfig
        from mem0.reranker.voyageai_reranker import VoyageAIReranker

        config = VoyageAIRerankerConfig(model="rerank-2")
        reranker = VoyageAIReranker(config)

        documents = [
            {"memory": "Python programming language"},
            {"memory": "Java programming language"},
        ]
        result = reranker.rerank("Python", documents)

        assert len(result) == 2
        assert result[0]["memory"] == "Python programming language"

    def test_rerank_2_lite_model(self):
        """Test rerank-2-lite model (faster, cheaper)."""
        from mem0.configs.rerankers.voyageai import VoyageAIRerankerConfig
        from mem0.reranker.voyageai_reranker import VoyageAIReranker

        config = VoyageAIRerankerConfig(model="rerank-2-lite")
        reranker = VoyageAIReranker(config)

        documents = [
            {"memory": "Document about technology"},
            {"memory": "Document about science"},
        ]
        result = reranker.rerank("tech industry news", documents)

        # Verify the lite model works and returns valid results
        assert len(result) == 2
        assert all("rerank_score" in doc for doc in result)
        assert all(0 <= doc["rerank_score"] <= 1 for doc in result)


class TestVoyageAITokenAwareBatchingIntegration:
    """Integration tests for token-aware batching."""

    def test_batch_small_texts(self):
        """Test batching with small texts that fit in one batch."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3.5")
        embedder = VoyageAIEmbedding(config)

        texts = [f"Short text number {i}" for i in range(10)]
        result = embedder.embed_batch(texts, memory_action="add")

        assert len(result) == 10
        assert all(len(emb) == 1024 for emb in result)

    def test_batch_with_custom_batch_size(self):
        """Test batching with custom batch size limit."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3.5", voyageai_batch_size=3)
        embedder = VoyageAIEmbedding(config)

        texts = ["Text A", "Text B", "Text C", "Text D", "Text E"]
        result = embedder.embed_batch(texts)

        # Should split into batches of 3, 2
        assert len(result) == 5

    def test_batch_preserves_order(self):
        """Test that batch embedding preserves input order."""
        import math

        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        def cosine_similarity(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b)

        config = BaseEmbedderConfig(model="voyage-3.5", voyageai_batch_size=2)
        embedder = VoyageAIEmbedding(config)

        texts = ["Apple fruit", "Banana fruit", "Car vehicle"]
        batch_results = embedder.embed_batch(texts)

        # Get individual embeddings to compare
        single_results = [embedder.embed(t) for t in texts]

        # Batch results should match single results (high similarity)
        for i in range(len(texts)):
            sim = cosine_similarity(batch_results[i], single_results[i])
            assert sim > 0.99, f"Embedding {i} doesn't match: similarity={sim}"

    def test_batch_with_long_texts(self):
        """Test batching with longer texts that use more tokens."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        config = BaseEmbedderConfig(model="voyage-3.5")
        embedder = VoyageAIEmbedding(config)

        # Create texts of varying lengths
        texts = [
            "Short text.",
            "This is a medium length text with more words to process.",
            "This is a longer piece of text that contains many more words and should "
            "use up more tokens when being processed by the embedding model. It includes "
            "multiple sentences and covers various topics to test the token counting.",
        ]
        result = embedder.embed_batch(texts)

        assert len(result) == 3
        assert all(len(emb) == 1024 for emb in result)

    def test_batch_context_model_token_limit(self):
        """Test that context model respects its lower token limit (32k)."""
        from mem0.configs.embeddings.base import BaseEmbedderConfig
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        # voyage-context-3 has 32k token limit per batch
        config = BaseEmbedderConfig(
            model="voyage-context-3",  # This will be used for regular embed
            voyageai_context_model="voyage-context-3",
        )
        embedder = VoyageAIEmbedding(config)

        # Test with multiple chunks
        chunks = [
            ["Introduction paragraph", "Background information"],
            ["Methods section", "Results section", "Discussion"],
        ]
        result = embedder.embed_contextualized(chunks)

        assert len(result) == 5  # 2 + 3 chunks


class TestVoyageAIFactoryIntegration:
    """Integration tests using the factory pattern."""

    def test_create_embedder_via_factory(self):
        """Test creating VoyageAI embedder through factory."""
        from mem0.utils.factory import EmbedderFactory

        embedder = EmbedderFactory.create(
            "voyageai", {"model": "voyage-3"}, None
        )

        result = embedder.embed("Test via factory")
        assert len(result) == 1024

    def test_create_reranker_via_factory(self):
        """Test creating VoyageAI reranker through factory."""
        from mem0.utils.factory import RerankerFactory

        reranker = RerankerFactory.create("voyageai", {"model": "rerank-2"})

        documents = [{"memory": "Test document"}]
        result = reranker.rerank("test", documents)
        assert len(result) == 1
        assert "rerank_score" in result[0]
