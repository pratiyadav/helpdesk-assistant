# IT Helpdesk Assistant (multi-tenant RAG)

Admins upload policy/runbook docs for their org. Employees ask questions and get streamed, cited
answers. If the docs don't cover it, the assistant says so and files a ticket via a `create_ticket` tool call.

## Run
```bash
cp .env.example .env        # add GEMINI_API_KEY and a JWT_SECRET
docker compose up --build   # API on :8000, docs at /docs
```
```bash
# 1. create an org + admin
curl -s localhost:8000/auth/register-org -H 'content-type: application/json' \
  -d '{"org_name":"Acme","email":"admin@acme.com","password":"correct-horse-1"}'
# 2. upload a doc (use the token from step 1)
curl -s localhost:8000/documents -H "Authorization: Bearer $TOKEN" -F file=@backend/sample_docs/vpn.md
# 3. ask (SSE stream)
curl -N localhost:8000/chat -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"How do I reset my VPN token?"}'
```

## Design
- **Tenancy:** `org_id` is read from the signed JWT, stored on every table, and filtered in every query.
  `backend/tests/test_tenancy.py` checks that no retrieval mode leaks across orgs. Stretch: Postgres RLS.
- **Retrieval:** pgvector cosine search + Postgres full-text, merged with reciprocal rank fusion (`app/retrieval.py`).
- **Generation:** prompt requires `[C<id>]` citations; only ids that were actually retrieved are returned as citations.
- **Tool use:** `create_ticket` arguments validated by Pydantic; on invalid output the model is re-asked (2 retries) before a safe fallback.
- **LLM layer:** `app/llm.py` defines a small provider protocol; Gemini is the first implementation.
- **Observability:** every request logs retrieved chunk ids, latency, tokens, and whether it was answered or ticketed (`GET /logs`).

## Evaluation
```bash
docker compose exec api python -m eval.run_eval --chunk-sizes 400,800,1200 --modes vector,keyword,hybrid
docker compose exec api python -m eval.run_eval --chunk-sizes 800 --modes hybrid --full --judge
```
Replace `eval/golden_set.jsonl` (48 rows) with 30-50 questions over your own documents, including
unanswerable ones. Paste the resulting table here and state the LLM judge's limits (same-family bias, noisy YES/NO).

chunk  size	  mode	hit@5	MRR
400	  vector	1.00	0.92
400	  keyword	1.00	0.86
400	  hybrid	1.00	0.94
800	  vector	1.00	0.95
800	  keyword	1.00	0.93
800	  hybrid	1.00	0.95
1200	vector	1.00	0.95
1200	keyword	1.00	0.93
1200	hybrid	1.00	0.95


38 answerable questions from a synthetic 48-question set. Hit@5 saturates at 1.00, so the set cannot separate the methods; keyword MRR varied by about 0.01 between runs. 