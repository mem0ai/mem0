import os
import tempfile
from unittest.mock import patch

import pytest

from mem0.memory.file_utils import (
    MAX_FILE_SIZE_BYTES,
    chunk_text,
    extract_text_from_file,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _write_tmp(suffix: str, content: str | bytes) -> str:
    """Write content to a temp file and return its path."""
    mode = "wb" if isinstance(content, bytes) else "w"
    with tempfile.NamedTemporaryFile(suffix=suffix, mode=mode, delete=False) as f:
        f.write(content)
        return f.name


# ── extract_text_from_file ────────────────────────────────────────────────────

class TestExtractTextFromFile:
    def test_txt_utf8(self):
        path = _write_tmp(".txt", "Hello, world!")
        try:
            assert extract_text_from_file(path) == "Hello, world!"
        finally:
            os.unlink(path)

    def test_txt_latin1_fallback(self):
        # bytes that are invalid UTF-8 but valid latin-1
        content = "Caf\xe9".encode("latin-1")
        path = _write_tmp(".txt", content)
        try:
            result = extract_text_from_file(path)
            assert "Caf" in result
        finally:
            os.unlink(path)

    def test_unsupported_extension_raises(self):
        path = _write_tmp(".csv", "a,b,c")
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                extract_text_from_file(path)
        finally:
            os.unlink(path)

    def test_file_exceeding_size_limit_raises(self):
        path = _write_tmp(".txt", "some content")
        try:
            with patch("mem0.memory.file_utils.os.path.getsize", return_value=MAX_FILE_SIZE_BYTES + 1):
                with pytest.raises(ValueError, match="exceeds the maximum allowed"):
                    extract_text_from_file(path)
        finally:
            os.unlink(path)

    def test_pdf_requires_pypdf(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("pypdf not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        path = _write_tmp(".pdf", b"%PDF-1.4 fake")
        try:
            with pytest.raises(ImportError, match="pypdf"):
                extract_text_from_file(path)
        finally:
            os.unlink(path)

    def test_docx_requires_python_docx(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("python-docx not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        path = _write_tmp(".docx", b"PK fake docx")
        try:
            with pytest.raises(ImportError, match="python-docx"):
                extract_text_from_file(path)
        finally:
            os.unlink(path)


# ── chunk_text ────────────────────────────────────────────────────────────────

class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "Short text."
        assert chunk_text(text, chunk_size=4000) == [text]

    def test_exact_chunk_size_returns_single_chunk(self):
        text = "a" * 4000
        chunks = chunk_text(text, chunk_size=4000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_two_paragraphs_fit_in_one_chunk(self):
        text = "Para one.\n\nPara two."
        chunks = chunk_text(text, chunk_size=4000)
        assert len(chunks) == 1

    def test_paragraphs_split_across_chunks(self):
        # Each paragraph is 300 chars; chunk_size=500 → fits 1 per chunk (300+300=600 > 500)
        para = "x" * 300
        text = f"{para}\n\n{para}\n\n{para}"
        chunks = chunk_text(text, chunk_size=500)
        # 3 paragraphs × 300 chars; two fit together (300+300=600 > 500), so each is alone
        assert len(chunks) == 3
        # All content preserved
        for chunk in chunks:
            assert "x" * 300 in chunk

    def test_oversized_paragraph_is_sentence_split(self):
        # Single paragraph larger than chunk_size, multiple sentences
        sentences = ["Word " * 50 + "." for _ in range(10)]  # ~255 chars each
        para = " ".join(sentences)  # ~2550 chars
        chunks = chunk_text(para, chunk_size=500)
        assert len(chunks) > 1
        # No chunk exceeds chunk_size by more than one sentence worth
        for chunk in chunks:
            assert len(chunk) <= 500 + 300  # reasonable tolerance

    def test_no_empty_chunks(self):
        text = "\n\n".join(["line"] * 20)
        chunks = chunk_text(text, chunk_size=50)
        assert all(c.strip() for c in chunks)

    def test_custom_chunk_size(self):
        text = "a" * 100
        chunks = chunk_text(text, chunk_size=30)
        # single paragraph larger than chunk_size → sentence split
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk) <= 130  # sentence-level tolerance

    def test_single_oversized_sentence_is_not_lost(self):
        # One paragraph containing a single sentence larger than chunk_size
        big_sentence = "x" * 5000
        chunks = chunk_text(big_sentence, chunk_size=4000)
        # The sentence must appear in some chunk (not silently dropped)
        combined = " ".join(chunks)
        assert "x" * 5000 in combined
