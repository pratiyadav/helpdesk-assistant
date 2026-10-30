import re

from .config import CANDIDATES, TOP_K
from .db import pool
from .embeddings import embed

# Every query below filters on c.org_id. That filter IS the tenancy boundary.


def vector_search(conn, org_id, qvec, k):
    return conn.execute(
        """SELECT c.id, c.content, d.filename FROM chunks c
           JOIN documents d ON d.id = c.document_id
           WHERE c.org_id = %s ORDER BY c.embedding <=> %s LIMIT %s""",
        (org_id, qvec, k)).fetchall()


def keyword_search(conn, org_id, query, k):
    words = re.findall(r"[A-Za-z0-9]+", query)
    if not words:
        return []
    tsq = " | ".join(words)  # OR semantics: natural-language questions rarely match every word
    return conn.execute(
        """SELECT c.id, c.content, d.filename FROM chunks c
           JOIN documents d ON d.id = c.document_id
           WHERE c.org_id = %s AND c.tsv @@ to_tsquery('english', %s)
           ORDER BY ts_rank_cd(c.tsv, to_tsquery('english', %s)) DESC LIMIT %s""",
        (org_id, tsq, tsq, k)).fetchall()


def rrf(result_lists, k=60):
    """Reciprocal rank fusion: score = sum over lists of 1 / (k + rank)."""
    scores, rows = {}, {}
    for lst in result_lists:
        for rank, row in enumerate(lst, start=1):
            scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (k + rank)
            rows[row["id"]] = row
    return [rows[i] for i in sorted(scores, key=scores.get, reverse=True)]


def retrieve(org_id: int, question: str, mode: str = "hybrid", top_k: int = TOP_K):
    qvec = embed([question])[0]
    with pool.connection() as conn:
        vec = vector_search(conn, org_id, qvec, CANDIDATES)
        if mode == "vector":
            return vec[:top_k]
        kw = keyword_search(conn, org_id, question, CANDIDATES)
    if mode == "keyword":
        return kw[:top_k]
    return rrf([vec, kw])[:top_k]
