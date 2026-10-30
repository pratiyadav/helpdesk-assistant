"""Requires a running Postgres (docker compose up db) and DATABASE_URL/JWT_SECRET env vars."""
import pytest

from app import ingest
from app.db import init_db, pool
from app.retrieval import retrieve


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()
    pool.open()
    yield
    pool.close()


def _org(name, text):
    with pool.connection() as conn:
        org = conn.execute("INSERT INTO orgs(name) VALUES (%s) RETURNING id", (name,)).fetchone()["id"]
    doc = ingest.create_document(org, "a.md")
    ingest.ingest_document(org, doc, "a.md", text.encode())
    return org


def test_orgs_never_see_each_others_chunks():
    a = _org("tenant-a", "ALPHA-SECRET: the vpn token portal is at alpha.example.com")
    b = _org("tenant-b", "BETA-SECRET: the vpn token portal is at beta.example.com")
    try:
        for mode in ("vector", "keyword", "hybrid"):
            assert all("BETA-SECRET" not in c["content"] for c in retrieve(a, "vpn token portal", mode))
            assert all("ALPHA-SECRET" not in c["content"] for c in retrieve(b, "vpn token portal", mode))
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM orgs WHERE id IN (%s,%s)", (a, b))
