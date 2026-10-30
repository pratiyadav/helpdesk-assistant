import io
import re

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .db import pool
from .embeddings import embed


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith((".md", ".txt")):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type (use .pdf, .md or .txt)")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Fixed-size windows that prefer to break at a paragraph, then a sentence, boundary."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind(". ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def create_document(org_id: int, filename: str) -> int:
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO documents(org_id, filename) VALUES (%s,%s) RETURNING id", (org_id, filename)
        ).fetchone()
    return row["id"]


def ingest_document(org_id: int, doc_id: int, filename: str, data: bytes,
                    size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> None:
    """Runs as a background task. Marks the document 'ready' or 'failed'."""
    try:
        chunks = chunk_text(extract_text(filename, data), size, overlap)
        if not chunks:
            raise ValueError("No extractable text")
        vecs = embed(chunks)
        rows = [(org_id, doc_id, i, c, v) for i, (c, v) in enumerate(zip(chunks, vecs))]
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks(org_id, document_id, ord, content, embedding) VALUES (%s,%s,%s,%s,%s)",
                    rows)
            conn.execute("UPDATE documents SET status='ready' WHERE id=%s AND org_id=%s", (doc_id, org_id))
    except Exception as e:  # noqa: BLE001
        with pool.connection() as conn:
            conn.execute("UPDATE documents SET status='failed', error=%s WHERE id=%s AND org_id=%s",
                         (str(e)[:500], doc_id, org_id))
