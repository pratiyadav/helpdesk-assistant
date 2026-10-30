"""Evaluation harness.

Usage (inside the api container):
  python -m eval.run_eval --chunk-sizes 400,800 --modes vector,keyword,hybrid
  python -m eval.run_eval --chunk-sizes 800 --modes hybrid --full --judge

Golden set format (eval/golden_set.jsonl), one JSON object per line:
  {"question": "...", "answerable": true,  "gold_snippet": "short exact phrase from the source doc"}
  {"question": "...", "answerable": false}
Keep gold_snippet short and inside a single sentence so chunk boundaries don't hide it.
"""
import argparse
import json
import time
from pathlib import Path

from app import ingest
from app.db import init_db, pool
from app.llm import get_llm
from app.rag import run_chat
from app.retrieval import retrieve

ROOT = Path(__file__).parent.parent
norm = lambda s: " ".join(s.lower().split())  # noqa: E731


def build_org(docs_dir: Path, size: int, overlap: int):
    with pool.connection() as conn:
        org = conn.execute("INSERT INTO orgs(name) VALUES (%s) RETURNING id", (f"eval-{size}-{int(time.time())}",)).fetchone()["id"]
        uid = conn.execute("INSERT INTO users(org_id,email,password_hash,role) VALUES (%s,%s,'x','admin') RETURNING id",
                           (org, f"eval-{org}@example.com")).fetchone()["id"]
    for p in sorted(docs_dir.iterdir()):
        if p.suffix in (".md", ".txt", ".pdf"):
            doc_id = ingest.create_document(org, p.name)
            ingest.ingest_document(org, doc_id, p.name, p.read_bytes(), size, overlap)
    return org, uid


def retrieval_metrics(org, items, mode, k):
    n = hits = 0
    rr = 0.0
    for it in items:
        if not it["answerable"]:
            continue
        n += 1
        res = retrieve(org, it["question"], mode, k)
        rank = next((i for i, c in enumerate(res, 1) if norm(it["gold_snippet"]) in norm(c["content"])), None)
        if rank:
            hits += 1
            rr += 1 / rank
    return hits / max(n, 1), rr / max(n, 1)


def judge_faithful(question, answer, cited):
    system = "You are a strict grader. Reply with exactly YES or NO."
    user = (f"Sources:\n{cited}\n\nAnswer:\n{answer}\n\nIs every factual claim in the answer supported by the sources? "
            f"Question was: {question}")
    return get_llm().complete(system, user).strip().upper().startswith("YES")


def generation_metrics(org, uid, items, mode, k, judge):
    refusal_ok = false_refusal = faithful = answered_n = ans_total = 0
    for it in items:
        events = list(run_chat(org, uid, it["question"], mode, k))
        refused = any(e["type"] == "ticket" for e in events)
        refusal_ok += refused == (not it["answerable"])
        if it["answerable"]:
            ans_total += 1
            false_refusal += refused
            if judge and not refused:
                answered_n += 1
                text = "".join(e["text"] for e in events if e["type"] == "token")
                cited = "\n".join(c["content"] for e in events if e["type"] == "citations" for c in e["citations"])
                faithful += judge_faithful(it["question"], text, cited)
        time.sleep(4)  # stay under free-tier rate limits
    out = {"refusal_accuracy": refusal_ok / len(items), "false_refusal_rate": false_refusal / max(ans_total, 1)}
    if judge:
        out["faithfulness"] = faithful / max(answered_n, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(ROOT / "sample_docs"))
    ap.add_argument("--golden", default=str(ROOT / "eval" / "golden_set.jsonl"))
    ap.add_argument("--chunk-sizes", default="800")
    ap.add_argument("--overlap", type=int, default=100)
    ap.add_argument("--modes", default="vector,keyword,hybrid")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--full", action="store_true", help="also run generation (uses LLM calls)")
    ap.add_argument("--judge", action="store_true", help="LLM-judge faithfulness (needs --full)")
    a = ap.parse_args()

    init_db()
    pool.open()
    items = [json.loads(l) for l in Path(a.golden).read_text().splitlines() if l.strip()]
    rows = ["| chunk size | mode | hit@%d | MRR | refusal acc | false refusal | faithfulness |" % a.k,
            "|---|---|---|---|---|---|---|"]
    for size in [int(s) for s in a.chunk_sizes.split(",")]:
        org, uid = build_org(Path(a.docs), size, a.overlap)
        try:
            for mode in a.modes.split(","):
                hit, mrr = retrieval_metrics(org, items, mode, a.k)
                g = generation_metrics(org, uid, items, mode, a.k, a.judge) if a.full else {}
                f = lambda key: f"{g[key]:.2f}" if key in g else "-"  # noqa: E731
                rows.append(f"| {size} | {mode} | {hit:.2f} | {mrr:.2f} | {f('refusal_accuracy')} | {f('false_refusal_rate')} | {f('faithfulness')} |")
        finally:
            with pool.connection() as conn:
                conn.execute("DELETE FROM orgs WHERE id=%s", (org,))  # cascades to users/docs/chunks
    table = "\n".join(rows)
    print(table)
    (ROOT / "eval" / "results.md").write_text(table + "\n")
    pool.close()


if __name__ == "__main__":
    main()
