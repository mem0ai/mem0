"""
Bailian Platform Model Integration Tests

Tests for LLM, Embedding, and Reranker components using Bailian platform models.
Configuration is passed via environment variables.

Environment Variables:
    BAILIAN_API_KEY       (required) Bailian (Dashscope) API key
    BAILIAN_LLM_MODEL     (optional) LLM model name, default: qwen3-max
    BAILIAN_EMBEDDER_MODEL(optional) Embedding model name, default: text-embedding-v4
    BAILIAN_EMBEDDER_DIMS (optional) Embedding dimensions, default: 1536
    BAILIAN_RERANKER_MODEL(optional) Reranker model name, default: qwen3-rerank
    BAILIAN_QDRANT_HOST   (optional) Qdrant host, default: localhost
    BAILIAN_QDRANT_PORT   (optional) Qdrant port, default: 6333
    BAILIAN_QDRANT_COLLECTION (optional) Qdrant collection name, default: test_bailian

Usage:
    BAILIAN_API_KEY=sk-xxx \
    BAILIAN_LLM_MODEL=qwen3-max \
    BAILIAN_EMBEDDER_MODEL=text-embedding-v4 \
    BAILIAN_EMBEDDER_DIMS=1536 \
    BAILIAN_RERANKER_MODEL=qwen3-rerank \
        pytest tests/test_bailian_models.py -v
"""

import json
import math
import os

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.bailian import BailianConfig
from mem0.configs.rerankers.bailian import BailianRerankerConfig
from mem0.embeddings.bailian import BaiLianEmbedding
from mem0.llms.bailian import BaiLianLLM
from mem0.reranker.bailian_reranker import bailian_reranker

# ===========================================================================
# Configuration from environment variables
# ===========================================================================
BAILIAN_CONFIG = {
    "api_key": os.environ.get("BAILIAN_API_KEY", ""),
    "llm_model": os.environ.get("BAILIAN_LLM_MODEL", "qwen3-max"),
    "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "embedder_model": os.environ.get("BAILIAN_EMBEDDER_MODEL", "text-embedding-v4"),
    "embedder_dims": int(os.environ.get("BAILIAN_EMBEDDER_DIMS", "1536")),
    "reranker_model": os.environ.get("BAILIAN_RERANKER_MODEL", "qwen3-rerank"),
    "reranker_base_url": "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
    "reranker_top_k": 3,
    "qdrant_host": os.environ.get("BAILIAN_QDRANT_HOST", "localhost"),
    "qdrant_port": int(os.environ.get("BAILIAN_QDRANT_PORT", "6333")),
    "qdrant_collection": os.environ.get("BAILIAN_QDRANT_COLLECTION", "test_bailian"),
}

SKIP_REASON = "Bailian API key not provided (set BAILIAN_API_KEY env var)"


def _cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ===========================================================================
# LLM Tests
# ===========================================================================
class TestBaiLianLLM:
    """Tests for BaiLian LLM via Dashscope."""

    @pytest.fixture(autouse=True)
    def setup(self):
        api_key = BAILIAN_CONFIG["api_key"]
        if not api_key:
            pytest.skip(SKIP_REASON)
        config = BailianConfig(
            model=BAILIAN_CONFIG["llm_model"],
            api_key=api_key,
            openai_base_url=BAILIAN_CONFIG["llm_base_url"],
            temperature=0.1,
            max_tokens=1000,
        )
        self.llm = BaiLianLLM(config)

    def test_bailian_llm_generate_response(self):
        """Test basic text generation capability."""
        messages = [
            {"role": "user", "content": "What is 2 + 3? Answer with just the number."}
        ]
        response = self.llm.generate_response(messages=messages)

        assert response is not None
        assert isinstance(response, str)
        assert len(response.strip()) > 0
        assert "5" in response

    def test_bailian_llm_json_response(self):
        """Test JSON format response generation."""
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that responds in JSON format.",
            },
            {
                "role": "user",
                "content": 'Return a JSON object with key "name" set to "Alice" and key "age" set to 30.',
            },
        ]
        response = self.llm.generate_response(
            messages=messages,
            response_format={"type": "json_object"},
        )

        assert response is not None
        assert isinstance(response, str)

        parsed = json.loads(response)
        assert "name" in parsed
        assert parsed["name"] == "Alice"
        assert "age" in parsed
        assert parsed["age"] == 30

    def test_bailian_llm_fact_extraction(self):
        """Test fact extraction scenario similar to mem0 usage."""
        fact_extraction_prompt = (
            "You are a Personal Information Organizer. "
            "Extract relevant facts from the conversation and return them "
            'in JSON format with a "facts" key containing a list of strings.\n\n'
            "Example:\n"
            'Input: Hi, my name is John. I am a software engineer.\n'
            'Output: {"facts": ["Name is John", "Is a Software engineer"]}'
        )
        messages = [
            {"role": "system", "content": fact_extraction_prompt},
            {
                "role": "user",
                "content": (
                    "Input:\n"
                    "My name is Alice, I live in Xihu District, Hangzhou. "
                    "I like drinking Latte, and I dislike Americano coffee."
                ),
            },
        ]
        response = self.llm.generate_response(
            messages=messages,
            response_format={"type": "json_object"},
        )

        assert response is not None
        parsed = json.loads(response)
        assert "facts" in parsed
        assert isinstance(parsed["facts"], list)
        assert len(parsed["facts"]) >= 2

        # Verify key facts are extracted
        facts_text = " ".join(parsed["facts"]).lower()
        assert "alice" in facts_text
        assert "hangzhou" in facts_text or "xihu" in facts_text


# ===========================================================================
# Embedding Tests
# ===========================================================================
class TestBaiLianEmbedding:
    """Tests for BaiLian Embedding."""

    @pytest.fixture(autouse=True)
    def setup(self):
        api_key = BAILIAN_CONFIG["api_key"]
        if not api_key:
            pytest.skip(SKIP_REASON)
        self.expected_dims = BAILIAN_CONFIG["embedder_dims"]
        config = BaseEmbedderConfig(
            model=BAILIAN_CONFIG["embedder_model"],
            api_key=api_key,
            embedding_dims=self.expected_dims,
        )
        self.embedder = BaiLianEmbedding(config)

    def test_bailian_embedding_single(self):
        """Test single text embedding returns correct dimensions."""
        text = "My name is Alice and I live in Hangzhou."
        embedding = self.embedder.embed(text)

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == self.expected_dims
        # Verify all elements are floats
        assert all(isinstance(v, float) for v in embedding)

    def test_bailian_embedding_batch(self):
        """Test batch embedding returns consistent dimensions."""
        texts = [
            "Alice likes drinking Latte.",
            "Bob prefers green tea.",
            "Charlie enjoys black coffee.",
        ]
        embeddings = self.embedder.batch_embed(texts)

        assert embeddings is not None
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        for emb in embeddings:
            assert len(emb) == self.expected_dims

    def test_bailian_embedding_similarity(self):
        """Test semantic similarity: similar texts should have higher cosine similarity."""
        text_a = "I like drinking coffee in the morning."
        text_b = "I enjoy having coffee when I wake up."
        text_c = "The stock market crashed yesterday."

        emb_a = self.embedder.embed(text_a)
        emb_b = self.embedder.embed(text_b)
        emb_c = self.embedder.embed(text_c)

        sim_ab = _cosine_similarity(emb_a, emb_b)
        sim_ac = _cosine_similarity(emb_a, emb_c)

        # Similar texts should have higher similarity
        assert sim_ab > sim_ac, (
            f"Expected similar texts to have higher similarity: "
            f"sim(a,b)={sim_ab:.4f} should be > sim(a,c)={sim_ac:.4f}"
        )
        # Similar texts should have reasonably high similarity
        assert sim_ab > 0.7, f"Expected sim(a,b) > 0.7, got {sim_ab:.4f}"


# ===========================================================================
# Reranker Tests
# ===========================================================================
class TestBaiLianReranker:
    """Tests for BaiLian Reranker."""

    @pytest.fixture(autouse=True)
    def setup(self):
        api_key = BAILIAN_CONFIG["api_key"]
        if not api_key:
            pytest.skip(SKIP_REASON)
        config = BailianRerankerConfig(
            model=BAILIAN_CONFIG["reranker_model"],
            api_key=api_key,
            api_url=BAILIAN_CONFIG["reranker_base_url"],
            top_k=BAILIAN_CONFIG["reranker_top_k"],
            return_documents=True,
        )
        self.reranker = bailian_reranker(config)

    def test_bailian_reranker_basic(self):
        """Test basic reranking returns results with rerank_score."""
        query = "What coffee does Alice like?"
        documents = [
            {"memory": "Alice likes drinking Latte."},
            {"memory": "Bob prefers Americano coffee."},
            {"memory": "Alice lives in Hangzhou."},
            {"memory": "Charlie enjoys green tea."},
        ]

        results = self.reranker.rerank(query=query, documents=documents)

        assert results is not None
        assert isinstance(results, list)
        assert len(results) > 0
        # Every result should have a rerank_score
        for doc in results:
            assert "rerank_score" in doc, f"Missing rerank_score in: {doc}"
            assert isinstance(doc["rerank_score"], (int, float))

    def test_bailian_reranker_relevance_order(self):
        """Test that more relevant documents rank higher than irrelevant ones."""
        query = "What coffee does Alice like?"
        documents = [
            {"memory": "Charlie enjoys green tea."},
            {"memory": "Alice likes drinking Latte."},
            {"memory": "The weather in Hangzhou is nice."},
            {"memory": "Bob prefers Americano coffee."},
        ]

        results = self.reranker.rerank(query=query, documents=documents)

        assert len(results) > 0

        # Build a score lookup by memory text
        score_map = {doc["memory"]: doc["rerank_score"] for doc in results}

        # The relevant document about Alice's coffee should score higher
        # than the clearly irrelevant weather document
        alice_score = score_map.get("Alice likes drinking Latte.", 0)
        weather_score = score_map.get("The weather in Hangzhou is nice.", 0)
        assert alice_score > weather_score, (
            f"Expected Alice's coffee doc to score higher than weather doc: "
            f"alice={alice_score:.4f} vs weather={weather_score:.4f}"
        )

        # Scores should be in descending order
        scores = [doc["rerank_score"] for doc in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not in descending order at index {i}: "
                f"{scores[i]} < {scores[i + 1]}"
            )

    def test_bailian_reranker_top_k(self):
        """Test that top_k parameter limits the number of results."""
        query = "What does Alice like?"
        documents = [
            {"memory": "Alice likes drinking Latte."},
            {"memory": "Alice lives in Hangzhou."},
            {"memory": "Alice dislikes Americano coffee."},
            {"memory": "Bob prefers green tea."},
            {"memory": "Charlie enjoys black coffee."},
        ]

        top_k = 2
        results = self.reranker.rerank(query=query, documents=documents, top_k=top_k)

        assert results is not None
        assert len(results) <= top_k, (
            f"Expected at most {top_k} results, got {len(results)}"
        )


# ===========================================================================
# Memory.from_config Integration Tests
# ===========================================================================
class TestMemoryFromConfig:
    """End-to-end tests using Memory.from_config with Bailian models and Qdrant vector store."""

    @pytest.fixture(autouse=True)
    def setup(self):
        api_key = BAILIAN_CONFIG["api_key"]
        if not api_key:
            pytest.skip(SKIP_REASON)

        from mem0 import Memory

        config = {
            "version": "v1.1",
            "llm": {
                "provider": "bailian",
                "config": {
                    "api_key": api_key,
                    "model": BAILIAN_CONFIG["llm_model"],
                    "enable_vision": False,
                },
            },
            "embedder": {
                "provider": "bailian",
                "config": {
                    "api_key": api_key,
                    "model": BAILIAN_CONFIG["embedder_model"],
                    "embedding_dims": BAILIAN_CONFIG["embedder_dims"],
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": BAILIAN_CONFIG["qdrant_collection"],
                    "host": BAILIAN_CONFIG["qdrant_host"],
                    "port": BAILIAN_CONFIG["qdrant_port"],
                },
            },
        }
        self.memory = Memory.from_config(config)
        self.user_id = "test_bailian_user"

        # Clean up before each test
        try:
            self.memory.delete_all(user_id=self.user_id)
        except Exception:
            pass

    def teardown_method(self):
        """Clean up after each test."""
        try:
            self.memory.delete_all(user_id=self.user_id)
        except Exception:
            pass

    def test_memory_add_and_get_all(self):
        """Test adding memories and retrieving them."""
        messages = [
            {
                "role": "user",
                "content": "My name is Alice, I live in Xihu District, Hangzhou.",
            }
        ]
        result = self.memory.add(messages=messages, user_id=self.user_id)

        assert result is not None
        assert "results" in result

        # Retrieve all memories
        all_memories = self.memory.get_all(user_id=self.user_id)
        assert all_memories is not None
        assert "results" in all_memories
        assert len(all_memories["results"]) > 0

    def test_memory_search(self):
        """Test adding memories and searching for them."""
        messages = [
            {
                "role": "user",
                "content": (
                    "I like drinking Latte coffee. "
                    "I dislike Americano. "
                    "My favorite programming language is Python."
                ),
            }
        ]
        self.memory.add(messages=messages, user_id=self.user_id)

        # Search for coffee preference
        search_result = self.memory.search(
            query="What coffee does the user like?",
            user_id=self.user_id,
        )

        assert search_result is not None
        assert "results" in search_result
        assert len(search_result["results"]) > 0

        # The top result should be related to coffee/Latte
        top_memory = search_result["results"][0]["memory"].lower()
        assert "latte" in top_memory or "coffee" in top_memory, (
            f"Expected top search result to mention Latte or coffee, got: {top_memory}"
        )

    def test_memory_update_and_delete(self):
        """Test updating and deleting a memory."""
        messages = [
            {"role": "user", "content": "My favorite color is blue."}
        ]
        add_result = self.memory.add(messages=messages, user_id=self.user_id)

        assert "results" in add_result
        assert len(add_result["results"]) > 0

        # Get the memory ID
        memory_id = add_result["results"][0].get("id")
        assert memory_id is not None

        # Update the memory
        update_result = self.memory.update(
            memory_id=memory_id, data="My favorite color is green."
        )
        assert update_result is not None

        # Verify the update
        updated_memory = self.memory.get(memory_id)
        assert "green" in updated_memory["memory"].lower()

        # Delete the memory
        delete_result = self.memory.delete(memory_id=memory_id)
        assert delete_result is not None

    def test_memory_from_config_with_reranker(self):
        """Test Memory.from_config with reranker enabled."""
        from mem0 import Memory

        config = {
            "version": "v1.1",
            "llm": {
                "provider": "bailian",
                "config": {
                    "api_key": BAILIAN_CONFIG["api_key"],
                    "model": BAILIAN_CONFIG["llm_model"],
                    "enable_vision": False,
                },
            },
            "embedder": {
                "provider": "bailian",
                "config": {
                    "api_key": BAILIAN_CONFIG["api_key"],
                    "model": BAILIAN_CONFIG["embedder_model"],
                    "embedding_dims": BAILIAN_CONFIG["embedder_dims"],
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": BAILIAN_CONFIG["qdrant_collection"] + "_reranker",
                    "host": BAILIAN_CONFIG["qdrant_host"],
                    "port": BAILIAN_CONFIG["qdrant_port"],
                },
            },
            "reranker": {
                "provider": "bailian",
                "config": {
                    "api_key": BAILIAN_CONFIG["api_key"],
                    "model": BAILIAN_CONFIG["reranker_model"],
                    "return_documents": True,
                    "top_k": BAILIAN_CONFIG["reranker_top_k"],
                },
            },
        }
        memory = Memory.from_config(config)
        user_id = "test_reranker_user"

        try:
            # Add multiple memories
            memory.add(
                messages=[{"role": "user", "content": "I love playing basketball on weekends."}],
                user_id=user_id,
            )
            memory.add(
                messages=[{"role": "user", "content": "My favorite food is sushi."}],
                user_id=user_id,
            )

            # Search with reranker
            result = memory.search(query="What sport does the user play?", user_id=user_id)

            assert result is not None
            assert "results" in result
            assert len(result["results"]) > 0

            top_memory = result["results"][0]["memory"].lower()
            assert "basketball" in top_memory or "sport" in top_memory, (
                f"Expected top result to mention basketball, got: {top_memory}"
            )
        finally:
            try:
                memory.delete_all(user_id=user_id)
            except Exception:
                pass
