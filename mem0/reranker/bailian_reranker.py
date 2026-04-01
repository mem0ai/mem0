import os
from typing import List, Dict, Any
import os
import requests
from mem0.reranker.base import BaseReranker


class bailian_reranker(BaseReranker):
    """Dashscope-based reranker implementation."""

    def __init__(self, config):
        """
        Initialize dashscope reranker.

        Args:
            config: DashscopeRerankerConfig object with configuration parameters
        """

        self.config = config
        self.api_key = (
            config.api_key
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("RERANKER_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "Dashscope API key is required. Set DASHSCOPE_API_KEY environment variable or pass api_key in config."
            )

        self.url = (
            config.api_url
            or os.getenv("DASHSCOPE_RERANKER_URL")
            or os.getenv("RERANKER_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
        )
        self.model = (
            config.model or os.getenv("RERANKER_CONFIG_MODEL") or "qwen3-rerank"
        )
        if self.model not in ["qwen3-rerank", "gte-rerank-v2"]:
            raise ValueError(
                "Invalid model name. Supported models are 'qwen3-rerank' and 'gte-rerank-v2'."
            )
        self.return_documents = config.return_documents or True

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using Dashscope's rerank API.

        Args:
            query: The search query
            documents: List of documents to rerank
            top_k: Number of top documents to return

        Returns:
            List of reranked documents with rerank_score
        """
        if not documents:
            return documents

        # Extract text content for reranking
        doc_texts = []
        for doc in documents:
            if "memory" in doc:
                doc_texts.append(doc["memory"])
            elif "text" in doc:
                doc_texts.append(doc["text"])
            elif "content" in doc:
                doc_texts.append(doc["content"])
            else:
                doc_texts.append(str(doc))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # prepare data
        data = {}
        if self.model == "qwen3-rerank":
            data = {
                "model": self.model,
                "documents": doc_texts,
                "query": query,
                "top_n": top_k or self.config.top_k or len(documents),
                "instruct": "Given a search query, retrieve relevant passages that answer the query.",
            }
        elif self.model == "gte-rerank-v2":
            data = {
                "model": self.model,
                "input": {"query": query, "documents": doc_texts},
                "parameters": {
                    "return_documents": self.return_documents,
                    "top_n": top_k or self.config.top_k or len(documents),
                },
            }
        else:
            raise ValueError(
                "Invalid model name. Supported models are 'qwen3-rerank' and 'gte-rerank-v2'."
            )

        try:
            # Call Bailian rerank API
            response = requests.post(self.url, headers=headers, json=data)

            # Check if request was successful
            response.raise_for_status()

            # Parse the response according to the actual structure
            response_data = response.json()

            if self.model == "qwen3-rerank":
                results = response_data.get("results", [])
            else:
                results = response_data.get("output", {}).get("results", [])

            # Create reranked results
            reranked_docs = []
            for result in results:
                index = result.get("index", 0)
                relevance_score = result.get("relevance_score", 0.0)
                document_text = result.get("document", {}).get("text", "")

                # Get the original document using the index
                if 0 <= index < len(documents):
                    original_doc = documents[index].copy()
                else:
                    # Fallback: find document by matching text content
                    original_doc = None
                    for i, doc in enumerate(documents):
                        doc_content = (
                            doc.get("memory")
                            or doc.get("text")
                            or doc.get("content")
                            or str(doc)
                        )
                        if doc_content == document_text:
                            original_doc = documents[i].copy()
                            break

                    if original_doc is None:
                        continue  # Skip if we can't match the document

                original_doc["rerank_score"] = relevance_score
                reranked_docs.append(original_doc)

            # Sort by relevance score in descending order
            reranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

            # Apply top_k limit
            if top_k:
                reranked_docs = reranked_docs[:top_k]
            elif self.config.top_k:
                reranked_docs = reranked_docs[: self.config.top_k]

            return reranked_docs

        except Exception as e:
            print(f"Error during reranking: {e}")
            # Fallback to original order if reranking fails
            for doc in documents:
                doc["rerank_score"] = 0.0
            return documents[:top_k] if top_k else documents
