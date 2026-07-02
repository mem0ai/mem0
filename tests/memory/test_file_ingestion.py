import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from mem0.memory.file_utils import _chunk_text, parse_file
from mem0.memory.main import AsyncMemory, Memory

FIXTURES = Path(__file__).parent / "fixtures"


def _write_docx(path, paragraphs):
    import docx

    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(str(path))


# --------------------------------------------------------------------------- #
# file_utils.parse_file
# --------------------------------------------------------------------------- #


def test_parse_txt(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("Alice lives in Paris.\n\nShe likes oat milk.", encoding="utf-8")
    chunks = parse_file(f)
    assert chunks == ["Alice lives in Paris.\n\nShe likes oat milk."]


def test_parse_markdown(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("# Heading\n\nBob works in Berlin.", encoding="utf-8")
    chunks = parse_file(f)
    assert "Bob works in Berlin." in "\n\n".join(chunks)


def test_parse_pdf():
    chunks = parse_file(FIXTURES / "sample.pdf")
    text = "\n\n".join(chunks)
    assert "Alice lives in Paris" in text
    assert "dark mode" in text


def test_parse_docx(tmp_path):
    f = tmp_path / "sample.docx"
    _write_docx(f, ["Carol is a designer.", "She lives in Tokyo."])
    text = "\n\n".join(parse_file(f))
    assert "Carol is a designer." in text
    assert "Tokyo" in text


def test_unsupported_extension_raises(tmp_path):
    f = tmp_path / "data.xyz"
    f.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_file(f)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_file(tmp_path / "nope.txt")


def test_empty_document_raises(tmp_path):
    f = tmp_path / "blank.txt"
    f.write_text("   \n\n   \t  ", encoding="utf-8")
    with pytest.raises(ValueError, match="No extractable text"):
        parse_file(f)


def test_corrupt_pdf_raises(tmp_path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"%PDF-1.4 not really a pdf at all")
    with pytest.raises(ValueError, match="Failed to read PDF"):
        parse_file(f)


def test_missing_pypdf_dependency_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)  # forces `import pypdf` to raise ImportError
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4")
    with pytest.raises(ImportError, match=r"mem0ai\[document\]"):
        parse_file(f)


def test_missing_python_docx_dependency_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    f = tmp_path / "doc.docx"
    f.write_bytes(b"PK")
    with pytest.raises(ImportError, match=r"mem0ai\[document\]"):
        parse_file(f)


# --------------------------------------------------------------------------- #
# _chunk_text: paragraph / sentence / hard-split tiers
# --------------------------------------------------------------------------- #


def test_chunk_packs_paragraphs():
    text = "\n\n".join(["para one", "para two", "para three"])
    assert _chunk_text(text, max_chunk_chars=1000) == ["para one\n\npara two\n\npara three"]


def test_chunk_sentence_fallback_for_big_paragraph():
    paragraph = " ".join([f"Sentence number {i}." for i in range(40)])
    chunks = _chunk_text(paragraph, max_chunk_chars=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_chunk_hard_split_for_oversized_sentence():
    chunks = _chunk_text("x" * 250, max_chunk_chars=100)
    assert len(chunks) == 3
    assert all(len(c) <= 100 for c in chunks)


def test_chunk_skips_blank_paragraphs():
    chunks = _chunk_text("real text\n\n   \n\n   ", max_chunk_chars=1000)
    assert chunks == ["real text"]


# --------------------------------------------------------------------------- #
# Memory.add(file=...) orchestration (mocked pipeline)
# --------------------------------------------------------------------------- #


def _setup_mocks(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)
    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())


def _silence_notices(mocker):
    mocker.patch("mem0.memory.main.detect_scale_threshold_from_add_result", return_value=None)
    for fn in ("display_first_run_notice", "display_scale_threshold_notice", "display_temporal_usage_notice"):
        mocker.patch(f"mem0.memory.main.{fn}", mocker.MagicMock())
    for fn in (
        "display_first_run_notice_async",
        "display_scale_threshold_notice_async",
        "display_temporal_usage_notice_async",
    ):
        mocker.patch(f"mem0.memory.main.{fn}", new_callable=AsyncMock)


@pytest.fixture
def sync_memory(mocker):
    _setup_mocks(mocker)
    _silence_notices(mocker)
    # Chunking is unit-tested separately; control chunk count here to test the loop.
    mocker.patch("mem0.memory.main.parse_file", return_value=["chunk one", "chunk two"])
    memory = Memory()
    memory._add_to_vector_store = mocker.MagicMock(return_value=[{"id": "1", "memory": "fact", "event": "ADD"}])
    return memory


@pytest.fixture
def two_chunk_file(tmp_path):
    # Two paragraphs, each its own chunk at a tiny chunk size.
    f = tmp_path / "doc.txt"
    f.write_text("First paragraph here.\n\nSecond paragraph here.", encoding="utf-8")
    return f


def test_add_file_calls_pipeline_per_chunk(sync_memory, two_chunk_file):
    result = sync_memory.add(file=two_chunk_file, user_id="u1", infer=False)
    assert sync_memory._add_to_vector_store.call_count == 2
    # aggregated, add()-shaped return
    assert list(result.keys()) == ["results"]
    assert len(result["results"]) == 2


def test_add_file_tags_source_file_metadata(sync_memory, two_chunk_file):
    sync_memory.add(file=two_chunk_file, user_id="u1")
    for call in sync_memory._add_to_vector_store.call_args_list:
        metadata = call.args[1]
        assert metadata["source_file"] == "doc.txt"


def test_add_file_caller_metadata_wins(sync_memory, two_chunk_file):
    sync_memory.add(file=two_chunk_file, user_id="u1", metadata={"source_file": "custom"})
    for call in sync_memory._add_to_vector_store.call_args_list:
        assert call.args[1]["source_file"] == "custom"


def test_add_file_passes_infer_flag(sync_memory, two_chunk_file):
    sync_memory.add(file=two_chunk_file, user_id="u1", infer=False)
    for call in sync_memory._add_to_vector_store.call_args_list:
        assert call.args[3] is False  # (messages, metadata, filters, infer, ...)


def test_add_file_and_messages_together_raises(sync_memory, two_chunk_file):
    with pytest.raises(Exception, match="not both"):
        sync_memory.add(messages="hi", file=two_chunk_file, user_id="u1")


def test_add_without_messages_or_file_raises(sync_memory):
    with pytest.raises(Exception, match="required"):
        sync_memory.add(user_id="u1")


# --------------------------------------------------------------------------- #
# AsyncMemory.add(file=...) parity
# --------------------------------------------------------------------------- #


@pytest.fixture
def async_memory(mocker):
    _setup_mocks(mocker)
    _silence_notices(mocker)
    mocker.patch("mem0.memory.main.parse_file", return_value=["chunk one", "chunk two"])
    memory = AsyncMemory()
    memory._add_to_vector_store = AsyncMock(return_value=[{"id": "1", "memory": "fact", "event": "ADD"}])
    return memory


@pytest.mark.asyncio
async def test_async_add_file_calls_pipeline_per_chunk(async_memory, two_chunk_file):
    result = await async_memory.add(file=two_chunk_file, user_id="u1", infer=False)
    assert async_memory._add_to_vector_store.call_count == 2
    assert len(result["results"]) == 2
    for call in async_memory._add_to_vector_store.call_args_list:
        assert call.args[1]["source_file"] == "doc.txt"


@pytest.mark.asyncio
async def test_async_add_file_and_messages_together_raises(async_memory, two_chunk_file):
    with pytest.raises(ValueError, match="not both"):
        await async_memory.add(messages="hi", file=two_chunk_file, user_id="u1")
