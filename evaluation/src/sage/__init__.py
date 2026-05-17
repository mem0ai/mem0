"""SAGE adapter for the LoCoMo memory-eval suite.

Treats SAGE (Sovereign Agent Governed Experience, github.com/l33tdawg/sage)
as a memory backend in the same shape as the existing RAG / langmem / zep
adapters. Seeds each conversation's raw turns into a per-conversation domain
inside a running SAGE node, retrieves via SAGE's hybrid recall (BM25 + vector
via RRF, optional cross-encoder rerank), then runs the same answer-generation
prompt the other backends use so the downstream LLM-judge metric is
apples-to-apples.

Architectural choice: turns are stored verbatim under BFT consensus, not
curated by an LLM step. This pairs SAGE's verified storage with the same
retrieval-and-answer pipeline the baseline adapters use.
"""

from .manager import SAGEManager

__all__ = ["SAGEManager"]
