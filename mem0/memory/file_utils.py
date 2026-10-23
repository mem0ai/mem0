"""Utilities for turning a document into text chunks for `Memory.add(file=...)`.

The parsers for PDF (``pypdf``) and DOCX (``python-docx``) are optional
dependencies, imported lazily so that installing them is only required when a
user actually ingests those formats. Plain text and Markdown use the stdlib.

Text is split into chunks (paragraph-first, sentence-fallback, hard-split for a
single oversized sentence) so each chunk is small enough for the add pipeline's
single extraction call, and large documents don't overflow the LLM context.
"""

import re
from pathlib import Path
from typing import List, Union

# Default chunk size in characters (~1k tokens). Kept as a module constant for
# v1; a configurable knob can follow if there is demand.
MAX_CHUNK_CHARS = 4000

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx"}


def get_source_name(file: Union[str, Path]) -> str:
    """Return the basename of a file path, for provenance metadata."""
    return Path(file).name


def parse_file(file: Union[str, Path], max_chunk_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Extract text from a document and split it into chunks.

    Args:
        file: Path to a ``.txt``/``.md``/``.pdf``/``.docx`` file.
        max_chunk_chars: Soft upper bound on the size of each chunk.

    Returns:
        A list of non-empty text chunks.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the extension is unsupported, the file cannot be read,
            or it contains no extractable text.
        ImportError: If the parser for the format is not installed.
    """
    path = Path(file)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        text = _read_text(path)
    elif extension == ".pdf":
        text = _read_pdf(path)
    elif extension == ".docx":
        text = _read_docx(path)
    else:
        raise ValueError(f"Unsupported file type '{extension}'. Supported types: {sorted(SUPPORTED_EXTENSIONS)}")

    chunks = _chunk_text(text, max_chunk_chars)
    if not chunks:
        raise ValueError(f"No extractable text found in '{path.name}'.")
    return chunks


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("Reading PDF files requires 'pypdf'. Install with: pip install 'mem0ai[document]'") from exc

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"Failed to read PDF '{path.name}': {exc}") from exc

    return "\n\n".join(pages)


def _read_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ImportError(
            "Reading DOCX files requires 'python-docx'. Install with: pip install 'mem0ai[document]'"
        ) from exc

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise ValueError(f"Failed to read DOCX '{path.name}': {exc}") from exc

    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def _chunk_text(text: str, max_chunk_chars: int) -> List[str]:
    """Split text paragraph-first, packing paragraphs up to ``max_chunk_chars``.

    A paragraph larger than the limit is broken down by sentences, and a single
    sentence still over the limit is hard-split so nothing exceeds the bound.
    """
    paragraphs = [para.strip() for para in re.split(r"\n\s*\n", text) if para.strip()]
    chunks: List[str] = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chunk_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_split_oversized(paragraph, max_chunk_chars))
        elif not buffer:
            buffer = paragraph
        elif len(buffer) + len(paragraph) + 2 <= max_chunk_chars:
            buffer = f"{buffer}\n\n{paragraph}"
        else:
            chunks.append(buffer)
            buffer = paragraph

    if buffer:
        chunks.append(buffer)

    return [chunk for chunk in chunks if chunk.strip()]


def _split_oversized(text: str, max_chunk_chars: int) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    buffer = ""

    for sentence in sentences:
        if len(sentence) > max_chunk_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(sentence[i : i + max_chunk_chars] for i in range(0, len(sentence), max_chunk_chars))
        elif not buffer:
            buffer = sentence
        elif len(buffer) + len(sentence) + 1 <= max_chunk_chars:
            buffer = f"{buffer} {sentence}"
        else:
            chunks.append(buffer)
            buffer = sentence

    if buffer:
        chunks.append(buffer)

    return chunks
