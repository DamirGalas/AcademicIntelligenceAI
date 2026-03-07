# Academic Intelligence AI — Production Roadmap

> Goal: Build a production-ready RAG system for academic information retrieval,
> covering all key competencies expected from an AI Engineer in practice.

---

## Checkpoint 1: Core Data Pipeline (ETL)

**Status: DONE**

The foundation — getting data from the web into a structured, searchable format.

- [x] HTML fetching from configured sources (`ingest/fetch_html.py`)
- [x] Config-driven source management (`config/config.yaml`)
- [x] HTML cleaning and text extraction with BeautifulSoup (`transform/html_to_text.py`)
- [x] Text chunking with overlap and word boundary respect (`transform/chunker.py`)
- [x] SQLite storage for documents and chunks (`load/load_documents.py`)
- [x] Embedding generation with Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
- [x] FAISS vector index creation and persistence
- [x] Full pipeline orchestration (`main.py`)

---

## Checkpoint 2: Pipeline Observability

**Status: DONE**

Knowing what the pipeline does — and when it breaks.

- [x] Centralized logging with config-driven level and file output (`monitoring/logger.py`)
- [x] Pipeline step tracking with timing and item counts (`monitoring/pipeline_tracker.py`)
- [x] SQLite tables for run history (`pipeline_runs`, `run_metrics`)
- [x] Chunk size drift detection with configurable threshold
- [x] Run comparison reports (`monitoring/report.py`)

---

## Checkpoint 3: Retrieval Engine

**Status: DONE**

Semantic search over indexed chunks.

- [x] Query encoding with the same embedding model used for indexing
- [x] L2 normalization for cosine similarity via inner product
- [x] FAISS search with top-k retrieval (`query/search.py`)
- [x] Configurable confidence threshold filtering

---

## Checkpoint 4: Retrieval Evaluation (AI)

**Status: DONE**

Measuring retrieval quality with quantitative metrics — a core AI engineering practice.

- [x] Ground truth test set with 20 annotated queries (`data/evaluation/test_queries.json`)
- [x] Precision@1, Precision@3, Fragment Hit@5, MRR metrics (`evaluation/retrieval_eval.py`)
- [x] Results: P@1=95%, P@3=95%, FragmentHit=75%, MRR=0.95

> **AI Note:** Evaluation is not optional. Without metrics you cannot improve a system —
> you are just guessing. Every change to chunking, embeddings, or retrieval must be
> validated against an eval set. This is the single most important habit for an AI engineer.

---

## Checkpoint 5: RAG Layer (AI)

**Status: DONE**

Retrieval-Augmented Generation — search + LLM = answer.

- [x] RAG orchestration: search -> prompt building -> LLM -> answer (`query/rag.py`)
- [x] LLM client for local Ollama/Mistral (`query/llm_client.py`)
- [x] System prompt in Serbian with strict context-only answering
- [x] Fallback response when no relevant chunks found
- [x] Interactive CLI for testing (`rag.py:run()`)

---

## Checkpoint 6: Query Observability (AI)

**Status: DONE**

Tracking what users ask and how the system responds.

- [x] `query_metrics` table in SQLite
- [x] Tracked fields: query, num_chunks, top_score, avg_top3_score, fallback, prompt_tokens, response_tokens, llm_latency_ms, total_latency_ms
- [ ] Observability deep-dive — before scaling up, fully understand every metric on the small dataset:
  - Why is confidence low for certain queries? Inspect the actual chunks returned.
  - What does avg_top3_score tell you that top_score alone does not?
  - When does fallback trigger — is the threshold correct or too aggressive?
  - How does latency break down (retrieval vs LLM vs total)?
  - Run 20-30 manual queries, read the metrics, and document what you learn.
  - Identify weak spots in the current system *before* adding more data.

> **AI Note:** Observability is not just "log everything and move on." The real skill is
> reading the data, understanding what it means, and acting on it. Scaling up with
> metrics you don't understand is like adding more servers to a system you can't debug.
> The small dataset is your lab — use it to build intuition before the data grows 100x.

---

## Checkpoint 7: System Specification

**Status: TODO**

Before scaling up, write down what we are building. Not a formal specification
document — a short, clear file that captures scope and success criteria so every
future checkpoint has a reference point.

- [ ] Write `docs/SPEC.md` (1-2 pages max) covering:
  - Target users: students, applicants, staff
  - 5-10 example questions the system must answer well (admissions, programs, news, schedules)
  - Data scope: which PMF pages/departments are in, which are out
  - Quality targets: P@1 >= X%, end-to-end answer accuracy >= X%, latency < X ms
  - Out of scope: what the system explicitly does NOT do
- [ ] Architecture diagrams (simple box-and-arrow, Mermaid or draw.io):
  - System context: the system as a black box with external actors (users, PMF website, LLM, storage)
  - Component diagram: ETL, vector store, retrieval, RAG orchestrator, config
  - Store in `docs/architecture/` and reference from SPEC
  - **Update these as the system evolves** — they are living documents, not upfront design

> Keep this lightweight. The goal is a reference point, not a bureaucratic artifact.
> If it takes more than one evening, you are over-engineering it.

---

## Checkpoint 8: Testing

**Status: TODO**

No tests = no confidence in changes. Testing comes *before* any new feature work
because everything from this point on involves changing core logic (chunking,
retrieval, prompts). Without tests, every change risks silently breaking what
already works — and you won't know until much later.

- [ ] pytest setup with fixtures for config, DB, and test data
  - A shared `conftest.py` with a temporary SQLite database, a small set of test HTML files,
    and a pre-built FAISS index over those files. This is the foundation all tests use.
- [ ] Unit tests for pure functions: chunker (split boundaries, overlap, edge cases),
  HTML cleaner (tag removal, whitespace normalization), prompt builder (template rendering)
  - These are fast, isolated tests. They catch regressions in the most-changed code.
- [ ] Integration tests: run the full pipeline (fetch -> clean -> chunk -> embed -> index)
  on a small set of local test HTML files and verify the output database and index are correct.
  - Use local files, not live URLs — tests must be deterministic and offline.
- [ ] Retrieval regression tests: run the eval set (`data/evaluation/test_queries.json`)
  against the current index and assert that P@1, MRR etc. are above defined thresholds.
  - This is the safety net for CP12-15. If someone changes chunking or retrieval and
    metrics drop, this test fails immediately.
- [ ] Test naming convention: `test_<module>_<behavior>.py` (e.g., `test_chunker_overlap.py`)

> **Why now and not later:** Every checkpoint from here on modifies core pipeline components.
> CP12 changes prompts, CP14 changes retrieval scoring, CP15 changes chunking — without
> regression tests, each of these changes is a gamble. Testing is not overhead; it is the
> mechanism that allows you to move fast without breaking things.

---

## Checkpoint 9: CI/CD & Code Quality

**Status: TODO**

CI/CD goes immediately after testing because tests without automation are tests
that stop being run. The goal: every push to the repo is automatically validated,
and no broken code reaches the main branch.

- [ ] GitHub Actions workflow: on every push and pull request, run:
  1. `ruff check` — linting (catches style issues, unused imports, common bugs)
  2. `mypy` — type checking (optional strictness, but at least check public interfaces)
  3. `pytest` — all unit and integration tests from CP8
  4. Retrieval eval — run `evaluation/retrieval_eval.py` and fail if metrics drop below
     the thresholds defined in CP7
- [ ] Pre-commit hooks (using the `pre-commit` framework):
  - `ruff format` — auto-format on commit so code style is never a discussion
  - `ruff check --fix` — auto-fix trivial lint issues
- [ ] Branch protection on `main`:
  - Require passing CI before merge
- [ ] Badge in README showing CI status

> **AI Note:** Retrieval eval in CI is an AI-specific practice. It is the equivalent of
> unit tests but for model/data quality. If someone changes the chunking strategy and
> P@1 drops from 95% to 60%, CI should catch that before it reaches production.

---

## Checkpoint 10: Incremental Pipeline & Deduplication

**Status: TODO**

The current pipeline drops and recreates the database on every run. Before
scaling to hundreds of pages, this must change — otherwise every crawl
re-embeds all existing content, wasting compute and time.

- [ ] Content hashing (SHA-256 of cleaned text) to detect duplicates and changes.
  - Hash is computed after HTML cleaning but before chunking.
  - Store the hash in the `documents` table alongside the URL.
- [ ] Incremental SQLite load:
  - New URL -> INSERT document + chunks
  - Existing URL, different hash -> UPDATE document, DELETE old chunks, INSERT new chunks
  - Existing URL, same hash -> SKIP entirely (no re-chunking, no re-embedding)
- [ ] Incremental FAISS index update:
  - Option A (simpler): rebuild index only from new/changed chunks, then merge with existing
  - Option B (production): use `faiss.IndexIDMap` to add/remove vectors by ID without full rebuild
  - Start with Option A, move to B if rebuild time becomes a bottleneck
- [ ] Metadata versioning:
  - `last_seen` timestamp — updated on every pipeline run where the URL is still live
  - `last_changed` timestamp — updated only when content hash changes
  - `first_indexed` timestamp — never changes, useful for debugging
- [ ] Soft delete for pages that disappear from the source:
  - If a URL was previously indexed but is no longer found in the crawl, mark it as
    `status = 'gone'` instead of deleting. Keep the data for debugging.

> **Why before the crawler:** If you build the crawler first, you'll run it, get 500 pages,
> and then realize every subsequent run re-processes all 500. Building incremental first
> means the crawler benefits from it immediately.

---

## Checkpoint 11: Scale — Web Crawler & Large Dataset (AI)

**Status: TODO**

The current system fetches 6 individual pages. A production system needs hundreds or
thousands of pages. This is the difference between a demo and a real system.

- [ ] Recursive web crawler with link discovery on the same domain:
  - Start from seed URLs in `config.yaml`
  - Extract all `<a href>` links from each page
  - Filter: only follow links within the same domain (e.g., `pmf.uns.ac.rs`)
  - Normalize URLs: strip fragments (`#section`), resolve relative paths, lowercase
- [ ] Configurable `max_depth` and `max_pages` per source
- [ ] Politeness:
  - Configurable delay between requests (e.g., 1-2 seconds)
  - Parse and respect `robots.txt` (use `urllib.robotparser`)
  - Set a descriptive `User-Agent` header
- [ ] URL normalization and deduplication:
  - Canonicalize URLs before inserting into the crawl queue
  - Cross-reference with the `documents` table to skip already-indexed unchanged pages (from CP10)
- [ ] Expand sources: more PMF departments, PDF documents, exam schedules
- [ ] Target: 500+ pages indexed
- [ ] After crawl completes: re-run retrieval eval (CP4) to verify quality didn't degrade

> **AI Note:** Data quality and quantity are the biggest levers in any AI system.
> A perfect retrieval engine over 6 pages is less useful than a decent one over 600.
> After scaling, expect eval metrics to change. More data means more noise, more
> edge cases, and potentially lower precision. This is normal — measure, then improve.

---

## Experiment Tracking — A Practice, Not a Checkpoint

From this point on (CP12-15), every change is an experiment. Instead of a separate
data versioning checkpoint, follow this rule for every experiment:

1. **Before:** commit your current code and note the current eval metrics
2. **Change:** modify one variable (chunk size, prompt, model, etc.)
3. **Measure:** run retrieval eval + RAG eval, record the results
4. **Decide:** keep or revert. Record the decision.

Track experiments in git commit messages with a consistent format:
```
experiment: chunk_size 500->300 | P@1: 95%->88% | MRR: 0.95->0.82 | REVERTED
experiment: add few-shot prompts | answer_accuracy: 72%->85% | KEPT
```

If this becomes painful (many experiments, large artifacts), adopt a proper
experiment log (`data/experiments.jsonl`) or DVC. But start simple.

> **AI Note:** Reproducibility is critical, but the mechanism should match the scale.
> Git commits are enough for a solo project with small data. DVC is for teams with
> hundreds of GB. Do not build infrastructure you do not yet need.

---

## Checkpoint 12: Prompt Engineering & LLM Quality (AI)

**Status: TODO**

The prompt is basic. This is the **highest-ROI improvement** you can make right
now — small prompt changes have outsized impact on answer quality, and the effort
is minimal compared to changing chunking or retrieval architecture.

- [ ] Few-shot examples in the system prompt:
  - Add 3-5 examples of (question, context, ideal_answer) directly in the prompt
  - These guide the LLM on tone, length, format, and when to say "I don't know"
  - Use real queries from your eval set as examples
- [ ] Source attribution — LLM cites which chunk(s) it used:
  - Include chunk IDs or source URLs in the prompt context
  - Instruct the LLM to reference them in the answer (e.g., "[Izvor: pmf.uns.ac.rs/informatika]")
- [ ] Structured output format:
  - Answer: the actual response to the user
  - Sources: list of source URLs used (from chunk metadata)
  - Confidence: high/medium/low based on retrieval scores
  - Parse this structured output in code for downstream use (API, logging)
- [ ] Chain-of-thought prompting for complex questions:
  - For multi-part questions ("Koji su predmeti na prvoj godini i ko ih predaje?"),
    instruct the LLM to reason step by step before giving the final answer
  - This reduces hallucination on complex queries
- [ ] Experiment with different LLM models and compare quality:
  - Mistral 7B (current), Llama 3, Gemma 2, or larger models if hardware allows
  - For each: run the same 50 queries, evaluate answers, compare latency and quality

> **AI Note:** Prompt engineering is not "trying random things." It is systematic
> experimentation: change one variable, measure the output, keep what works.
> This checkpoint is deliberately placed first among the AI improvements because
> it gives the biggest quality jump for the least code change.

---

## Checkpoint 13: End-to-End RAG Evaluation (AI)

**Status: TODO**

Retrieval eval (CP4) measures whether the right chunks come back. But that is only
half the story — the actual product is the **final answer**. A system can retrieve
perfect chunks and still produce a wrong answer if the LLM hallucinates, misreads
context, or formats badly. This checkpoint builds the evaluation that measures what
the user actually sees.

- [ ] Build an answer evaluation dataset:
  - 50+ pairs of (question, expected_answer) covering all use case categories from CP7
  - Include edge cases: ambiguous questions, multi-part questions, questions with no answer,
    questions in different phrasings
  - Store in `data/evaluation/test_answers.json`
- [ ] Automated evaluation metrics:
  - **Faithfulness**: is the answer grounded in the retrieved context? (no hallucination)
  - **Answer relevancy**: does the answer actually address the question?
  - **Correctness**: does the answer match the expected answer in substance?
  - Implementation: use LLM-as-judge — a second LLM call that rates each answer on these
    dimensions. Define a clear rubric (1-5 scale or categorical).
- [ ] Hallucination detection:
  - Compare key claims in the LLM answer against retrieved chunks
  - Flag claims not grounded in context (entities, dates, numbers that don't appear in chunks)
  - Simple approach: extract named entities from answer, check presence in chunks
- [ ] Baseline measurement:
  - Run the full eval on the current system (CP5 prompts, CP3 retrieval)
  - Record: faithfulness %, relevancy %, correctness %, hallucination rate
  - This becomes the baseline that all future changes (CP14-16) are measured against
- [ ] Add RAG eval to CI (extend CP9):
  - Run end-to-end eval alongside retrieval eval
  - Fail if faithfulness or correctness drops below threshold

> **AI Note:** Retrieval eval tells you "did the system find the right information?"
> RAG eval tells you "did the system give the right answer?" You need both.
> Teams that only measure retrieval are optimizing a component, not the product.
> The user does not care about P@1 — they care whether the answer is correct.

---

## Checkpoint 14: Advanced Retrieval & Embeddings (AI)

**Status: TODO**

Moving beyond basic vector search to production-grade retrieval. This includes
both the retrieval algorithm and the embedding model — both determine what the
system can find.

### Embedding model experiments
- [ ] Benchmark alternative embedding models on your eval set:
  - Current: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim, fast, decent multilingual)
  - `multilingual-e5-large` — stronger multilingual performance, 1024 dim
  - `BGE-M3` — state-of-the-art multilingual, supports dense + sparse retrieval
  - For each: re-embed all chunks, rebuild index, run retrieval eval + RAG eval
  - Pick the model with the best quality/speed tradeoff for your data

### Hybrid search
- [ ] Combine semantic (FAISS) + keyword (BM25) scoring:
  - Semantic search is great for paraphrases ("when is the entrance exam" matches
    "prijemni ispit termin") but misses exact keyword matches
  - BM25 is great for exact terms ("JMBG", "OAS-INF", specific professor names)
  - Combine: retrieve top-50 from each, merge with weighted score (e.g., 0.7 * semantic + 0.3 * BM25)
  - Use `rank_bm25` Python library or build a simple inverted index

### Re-ranking
- [ ] Cross-encoder re-ranking:
  - First stage: fast retrieval (top-50 candidates from hybrid search)
  - Second stage: cross-encoder scores each (query, chunk) pair for relevance
  - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (small, fast, multilingual-capable)
  - Return top-5 re-ranked results to the LLM
  - This is one of the highest-impact improvements in RAG — cross-encoders are far
    more accurate than bi-encoder similarity but too slow for the first stage

### Query expansion
- [ ] If the user query is short or ambiguous, use the LLM to generate 2-3 alternative
  phrasings, search with all of them, and merge results
  - Example: "rokovi" -> "ispitni rokovi januar", "raspored ispita", "termini polaganja"

### Index scaling
- [ ] At 50K+ vectors, switch from `IndexFlatIP` to `IndexIVFFlat` or `IndexHNSWFlat`
  - Benchmark both on your data and pick based on speed/accuracy tradeoff

- [ ] Update evaluation set to cover new data sources and edge cases
- [ ] Re-run retrieval eval + RAG eval after each change — no blind upgrades

> **AI Note:** The pattern for production retrieval is:
> fast recall (top-50) -> accurate re-ranking (top-5) -> LLM generation.
> Each stage trades speed for accuracy. This is called a "retrieval funnel" and it is
> the standard architecture in industry. The embedding model is the foundation of
> the entire funnel — a better model lifts everything above it.

---

## Checkpoint 15: Advanced Chunking (AI)

**Status: TODO**

Character-based sliding window is a starting point. Production systems need
smarter chunking that respects document structure. This is placed **after**
prompt and retrieval improvements because it requires the most effort and its
impact is data-dependent — you may find that better prompts and retrieval
already solve most of your quality issues.

- [ ] HTML structure-aware chunking:
  - Split by semantic boundaries: `<h1>`, `<h2>`, `<h3>` headings, `<p>` paragraphs, `<ul>`/`<ol>` lists
  - Each chunk should ideally correspond to one "topic" or "section"
  - Preserve heading hierarchy: if a chunk comes from a `<h2>` section under a `<h1>`,
    prepend the `<h1>` title as context (e.g., "Informatika > Prijemni ispit > ...")
- [ ] Metadata enrichment per chunk:
  - Source URL, section title, page title, date if available
  - Stored in SQLite, used for filtering and display
- [ ] Chunk size tuning — run experiments:
  - Try 200, 300, 500, 800 character chunks
  - For each: rebuild index, run retrieval eval + RAG eval, record in git commit
  - The "best" size depends on your data — academic pages with dense tables need
    different chunking than pages with long prose paragraphs
- [ ] Overlap tuning:
  - Try 0%, 10%, 20%, 30% overlap
  - More overlap = more chunks = larger index = slower search, but potentially better recall
- [ ] After all experiments: pick the best config, document the decision

> **AI Note:** Chunking strategy directly impacts retrieval quality. There is no universal
> best setting — you must experiment, measure with your eval set, and iterate.
> But do not start here — fix prompts and retrieval first, then tune chunking for
> the remaining quality gaps.

---

## Checkpoint 16: Agentic RAG (AI)

**Status: TODO**

The current system is single-pass: query -> search -> prompt -> LLM -> answer.
An agentic system can reason, plan, and use tools across multiple steps to
handle complex questions.

This checkpoint comes *before* the API, Safety, and Monitoring layers because
the agent loop fundamentally changes the system architecture. An agent makes
multiple LLM calls, multiple searches, and produces a reasoning trace — all of
which affect how you design:
- **API**: needs streaming support and a richer response model with agent steps
- **Safety**: prompt injection checks must run at *every* agent step
- **Monitoring**: must track multi-step execution, not just single-pass latency
- **Cost**: one user query can trigger 3-5 LLM calls

- [ ] **Agent flow diagram** — before writing code, draw the agent architecture:
  - The agent loop: think -> act -> observe -> decide (continue or answer)
  - Decision points: when does the agent re-search? when does it give up?
  - Tool catalog: which tools can the agent call (search, lookup, date check)?
  - Guard rails: where are the exit conditions (max steps, timeout, token budget)?
  - Store in `docs/architecture/`
- [ ] Agent loop: LLM decides what to do next (search, answer, ask for clarification)
  - Start with the simplest useful agent: "search, check confidence, re-search if low"
  - This 2-step pattern alone covers a large class of failed queries
- [ ] Multi-step retrieval — agent breaks complex questions into sub-queries:
  - Example: "Uporedi predmete na informatici i matematici" -> two separate searches,
    then combine results
- [ ] Query rewriting — agent reformulates the query if first search returns low-confidence results
- [ ] Tool use: agent can call search, lookup specific document, check date, etc.
  - Define tools as functions with clear input/output schemas
- [ ] Reasoning trace — log each agent step (thought, action, observation) for debugging
- [ ] Guard rails — max iterations (e.g., 5), timeout (e.g., 15s), token budget per query
- [ ] **Latency budget**: define acceptable response times:
  - Single-pass queries: < 5 seconds
  - Agent multi-step queries: < 15 seconds
  - Measure and optimize against these targets

> **AI Note:** Agentic RAG is the current industry direction. Single-pass RAG fails on
> complex questions that require multiple lookups or query decomposition. Start simple —
> even a 2-step "search, then re-search if confidence is low" agent is a major improvement.

---

## Checkpoint 17: API Layer & Caching

**Status: TODO**

A CLI is for development. Production systems expose an API. Because the agent (CP16)
is already built, the API handles multi-step responses from the start.

- [ ] FastAPI application with `/ask` endpoint:
  - POST request with `{ "query": "..." }`
  - Response: `{ "answer": "...", "sources": [...], "confidence": "...", "agent_steps": [...], "latency_ms": ... }`
  - Use the Agent pipeline from CP16 as the backend
- [ ] Streaming support:
  - Agent responses can take several seconds (multiple LLM calls)
  - Use Server-Sent Events (SSE) to stream intermediate steps and final answer
- [ ] Request/response models with Pydantic:
  - Input validation: query must be non-empty string, max length (e.g., 500 chars)
  - Response model includes agent trace, sources, and confidence
- [ ] **Response caching**:
  - Cache frequent queries (hash the query, store answer + TTL)
  - If 50 students ask "Kada je prijemni?", call the LLM once, not 50 times
  - Simple implementation: in-memory dict or SQLite cache table with expiry
  - Invalidate cache when the pipeline re-indexes relevant content
- [ ] Health check endpoint (`/health`):
  - Returns 200 if FAISS index is loaded, DB is accessible, and LLM is reachable
  - Returns 503 with details if any component is down
- [ ] Rate limiting:
  - Limit requests per IP (e.g., 10/minute)
  - Token budget per request (accounts for multi-step agent cost)
- [ ] CORS configuration for the frontend domain (CP22)

---

## Checkpoint 18: Safety & Guardrails (AI)

**Status: TODO**

A RAG system that anyone can query must handle adversarial input, hallucinations,
and data leakage. With the agent loop (CP16), each agent step is a potential
attack surface.

- [ ] Prompt injection protection:
  - Approach 1: keyword/pattern blocklist for common injection phrases
  - Approach 3: sandwich defense — repeat system instructions after user input
  - **Agent-specific**: run injection checks on the initial query AND on intermediate
    content the agent processes (retrieved chunks could contain injection attempts)
  - Start with 1 + 3, add LLM-based classification if needed
- [ ] Input sanitization:
  - Reject empty queries, queries over max length
  - Strip HTML/script tags from input
- [ ] Output validation — verify LLM answer is grounded in retrieved chunks:
  - **Agent-specific**: validate at each agent step, not just the final answer
- [ ] PII filtering:
  - Scan source data during ingestion for personal info (emails, phone numbers, JMBG)
  - Scan LLM output before returning to user — redact any PII that leaks through
- [ ] Content boundary enforcement:
  - System answers only about PMF/academic topics
  - Refuses off-topic requests
- [ ] Logging of blocked/flagged queries for review

> **AI Note:** Safety is not a feature you add at the end — it is a production requirement.
> With an agent loop, the attack surface multiplies — each step where the LLM processes
> external content is a potential injection point.

---

## Checkpoint 19: Containerization & Deployment

**Status: TODO**

Making the system runnable anywhere, not just on your machine.

- [ ] **Deployment diagram** — before writing Dockerfiles, draw how the system runs:
  - Containers (app, ollama), networking, volumes, ports, health checks
  - Store in `docs/architecture/`
- [ ] Dockerfile for the application:
  - Multi-stage build: build stage (install dependencies) + runtime stage (slim image)
  - Pin Python version, use `.dockerignore`
- [ ] Docker Compose with app + Ollama:
  - `docker compose up` starts the entire system
  - Internal networking between app and ollama
- [ ] Environment-based configuration (dev / prod):
  - Dev: debug logging, no rate limiting
  - Prod: info logging, rate limiting, health checks active
- [ ] Volume mounts for persistent data (SQLite, FAISS index, Ollama models)
- [ ] Health checks + restart policy (`restart: unless-stopped`)
- [ ] README with deployment instructions

---

## Checkpoint 20: Backup & Recovery

**Status: TODO**

Production systems fail. The critical data is the SQLite database and the FAISS
index — both are files that can be backed up simply.

- [ ] Automated backup script:
  - Cron job that copies `data/academic.db` + `data/faiss_index/` to a backup location
  - Before every pipeline run: snapshot DB + index
  - Keep last 7 daily + 4 weekly backups, rotate old ones
- [ ] Consistency check after each pipeline run:
  - Verify number of vectors in FAISS matches number of chunks in SQLite
  - `PRAGMA integrity_check` as part of health check
- [ ] Document recovery steps for each failure scenario:
  - Corrupted DB: restore from backup, re-run pipeline for delta
  - Corrupted FAISS: rebuild from DB (re-embed all chunks)
  - Bad crawl: rollback to pre-crawl snapshot

> Keep this simple. Two files, one cron job, one consistency check. Scale the
> backup strategy when the system scale demands it.

---

## Checkpoint 21: Production Monitoring & Drift Detection (AI)

**Status: TODO**

AI systems degrade *silently* — no errors, no crashes, just gradually worse answers.
With the agent loop (CP16), monitoring tracks multi-step execution, not just
single-pass latency.

- [ ] Dashboard for query metrics:
  - Latency distribution (p50, p95, p99) — including per-agent-step breakdown
  - Fallback rate over time
  - Confidence score distribution
  - Agent step distribution (avg steps per query, timeout rate)
  - Query volume over time
  - Tool options: Grafana + SQLite exporter, or a simple HTML dashboard
- [ ] Data drift detection:
  - Monitor source websites for structural changes (new HTML layout breaks parser)
  - Compare chunk statistics across pipeline runs: avg chunk size, num chunks per page
  - Alert if statistics deviate from baseline
- [ ] Model performance monitoring:
  - Schedule retrieval eval + RAG eval to run weekly
  - Track P@1, MRR, faithfulness, correctness over time
  - Alert if any metric drops below threshold
- [ ] Alerting on anomalies:
  - Spike in fallback rate, drop in confidence, pipeline failures
  - Agent loop hitting max iterations too frequently
  - Alerts via email, Slack webhook, or monitored log
- [ ] Scheduled pipeline runs:
  - Cron job to crawl, update index, run eval, report results

> **AI Note:** Continuous monitoring and scheduled re-evaluation are how production AI
> systems stay reliable. This is called "MLOps" even for RAG systems.

---

## Checkpoint 22: Frontend & User Feedback

**Status: TODO**

Without a user interface, the system has no end users. Start simple. The most
important addition beyond display is a **feedback mechanism** — this is what
closes the loop and lets the system improve from real usage.

- [ ] MVP: Streamlit or Gradio app
  - Single text input for the query
  - Display: answer, sources (clickable links), confidence indicator
  - Conversation history within a session
  - Show agent reasoning steps (collapsible) for transparency
- [ ] **User feedback mechanism**:
  - Thumbs up/down on each answer
  - "This is incorrect" button with optional free-text correction
  - Store feedback in a `user_feedback` table (query, answer, rating, correction, timestamp)
  - Use negative feedback to:
    - Expand the eval set with real failure cases
    - Identify weak spots in retrieval or prompts
    - Prioritize which queries to improve
  - This is the **most valuable data source** for system improvement
- [ ] UX essentials:
  - Show "I don't know" clearly, not as a failure
  - Display source links so users can verify answers
  - Suggested questions to help users discover capabilities
- [ ] Accessibility:
  - Serbian language interface
  - Works on mobile (students use phones)
  - Fast load time

> **Note:** Start with Streamlit — it is purpose-built for ML demos and deploys in minutes.
> The feedback mechanism is more important than the UI polish. A ugly app with feedback
> improves; a beautiful app without feedback stagnates.

---

## Summary

| Checkpoint | Topic | Status |
|------------|-------|--------|
| 1 | Core Data Pipeline | DONE |
| 2 | Pipeline Observability | DONE |
| 3 | Retrieval Engine | DONE |
| 4 | Retrieval Evaluation (AI) | DONE |
| 5 | RAG Layer (AI) | DONE |
| 6 | Query Observability (AI) | DONE |
| 7 | System Specification | TODO |
| 8 | Testing | TODO |
| 9 | CI/CD & Code Quality | TODO |
| 10 | Incremental Pipeline & Deduplication | TODO |
| 11 | Scale — Crawler & Large Dataset (AI) | TODO |
| — | *Experiment Tracking (practice, not checkpoint)* | — |
| 12 | Prompt Engineering & LLM Quality (AI) | TODO |
| 13 | End-to-End RAG Evaluation (AI) | TODO |
| 14 | Advanced Retrieval & Embeddings (AI) | TODO |
| 15 | Advanced Chunking (AI) | TODO |
| 16 | Agentic RAG (AI) | TODO |
| 17 | API Layer & Caching | TODO |
| 18 | Safety & Guardrails (AI) | TODO |
| 19 | Containerization & Deployment | TODO |
| 20 | Backup & Recovery | TODO |
| 21 | Production Monitoring & Drift (AI) | TODO |
| 22 | Frontend & User Feedback | TODO |

**Current progress: Checkpoints 1-6 complete (foundation). Checkpoints 7-22 ahead (production).**

Checkpoints marked with **(AI)** are competencies that separate an AI engineer from a
software engineer who uses AI libraries. They require experimentation, measurement, and
an understanding of why things work — not just how to call the API.

### Key changes from original plan:
- **CP7 simplified** — lightweight spec instead of formal requirements document
- **CP12-15 reordered** — prompts first (highest ROI), then RAG eval, then retrieval, then chunking last
- **End-to-End RAG Evaluation added (CP13)** — measures actual answer quality, not just retrieval
- **Embedding model experiments added (CP14)** — one of the biggest levers for non-English RAG
- **Experiment tracking** — a practice rule (git commits), not a separate checkpoint
- **Caching added (CP17)** — critical for production cost and latency
- **User feedback added (CP22)** — closes the improvement loop
- **CP20 simplified** — proportional to actual system complexity
