import os
from typing import List

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)


def _extract_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required for PDF support. Install it with: pip install pypdf")

    text_parts = []
    reader = PdfReader(file_path)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            return f.read()


def _extract_docx(file_path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is required for DOCX support. Install it with: pip install python-docx")

    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def chunk_text(text: str, chunk_size: int = 4000) -> List[str]:
    if len(text) <= chunk_size:
        return [text]

    # split into natural paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        if para_size > chunk_size:
            # paragraph itself is too large — split on sentences
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            sentences = para.replace(". ", ".\n").split("\n")
            sentence_chunk = []
            sentence_size = 0

            for sentence in sentences:
                if sentence_size + len(sentence) > chunk_size and sentence_chunk:
                    chunks.append(" ".join(sentence_chunk))
                    sentence_chunk = []
                    sentence_size = 0
                sentence_chunk.append(sentence)
                sentence_size += len(sentence)

            if sentence_chunk:
                chunks.append(" ".join(sentence_chunk))

        elif current_size + para_size > chunk_size and current_chunk:
            # adding this paragraph would exceed limit — flush current chunk
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_size = para_size

        else:
            current_chunk.append(para)
            current_size += para_size

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return [c for c in chunks if c]
