# Academic Intelligence AI — Production Roadmap

> Goal: Build a production-ready RAG system for academic information retrieval,
> covering all key competencies expected from an AI Engineer in practice.

---

## Execution Phases — Overview

```
PHASE 0: Foundation (CP1-7) — DONE
  Core pipeline + observability + retrieval + RAG + spec — built on 6 test pages
  ↓
PHASE 1: Scale the data (CP8-11)
  Crawl (done) → filter & categorize → pipeline on full dataset → re-evaluate
  ↓
PHASE 2: Answer quality (CP12 + CP13 — iterative)
  E2E eval baseline FIRST ←→ GPT-4o-mini + tool calling + prompt engineering
  ↓
PHASE 3: Validate & Extend (CP14-15)
  Minimal frontend → user feedback → Agentic RAG (natural extension of CP13)
  ↓
PHASE 4: Robustness (CP16-18)
  Tests → CI/CD → architecture diagrams (document what exists, not what might exist)
  ↓
PHASE 5: Optimization — conditional, based on eval results (CP19-20)
  Better retrieval (if eval says retrieval is weak)
  Better chunking (if eval says chunking is weak)
  ↓
PHASE 6: Production (CP21-27)
  Incremental pipeline → API → safety → deploy → backup → monitoring → full frontend
```

**Key principles:**
- Eval (CP12) runs alongside optimization (CP13), not after — you need a baseline first
- Mini frontend comes early (Phase 3) to validate product value before investing in robustness
- Agentic RAG (CP15) follows tool calling (CP13) immediately — same mechanic, natural progression
- Tests come after scaling because testing a pipeline that's about to change is wasted work
- Architecture diagrams document what exists, drawn after the system stabilizes
- CP19/CP20 are conditional — only do them if eval shows specific weaknesses
- Incremental pipeline moves to production phase — first full run doesn't need it

---

# Phase 0: Foundation

*Built on 6 hand-picked test pages. Validates the core approach before scaling.*

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

- [x] Ground truth test set with 20 annotated queries (`data/evaluation/benchmark.json`)
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
- [x] Observability deep-dive — before scaling up, fully understand every metric on the small dataset:
  - Why is confidence low for certain queries? Inspect the actual chunks returned.
  - What does avg_top3_score tell you that top_score alone does not?
  - When does fallback trigger — is the threshold correct or too aggressive?
  - How does latency break down (retrieval vs LLM vs total)?
  - Run 20-30 manual queries, read the metrics, and document what you learn.
  - Identify weak spots in the current system *before* adding more data.
  - **Findings (2026-03-09):** 12 manual queries, 50% fallback rate. Threshold 0.50
    too aggressive for generic queries. avg_top3 ≈ top_score (uniform chunk quality).
    LLM is the bottleneck (31s avg), retrieval fast (~2s). Some fallbacks are
    unjustified (data exists but embedding misses paraphrases/typos).

> **AI Note:** Observability is not just "log everything and move on." The real skill is
> reading the data, understanding what it means, and acting on it. Scaling up with
> metrics you don't understand is like adding more servers to a system you can't debug.
> The small dataset is your lab — use it to build intuition before the data grows 100x.

---

## Checkpoint 7: System Specification

**Status: DONE**

Before scaling up, write down what we are building. Not a formal specification
document — a short, clear file that captures scope and success criteria so every
future checkpoint has a reference point.

- [x] Write `docs/SPEC.md` covering:
  - [x] Target users: enrolled students and prospective students (applicants considering PMF)
  - [x] Example questions: 40 questions in `docs/ASSUMED_QUESTIONS.md` (30 typical + 10 hard RAG eval)
  - [x] Data scope: 6 crawled domains defined, in/out of scope documented
  - [x] Out of scope: system explicitly does NOT do (Section 10 in SPEC.md)
  - [x] Quality targets (finalized):
    - P@1 ≥ 90% (strict: is top-1 result relevant?)
    - Precision@3 ≥ 80% (strict: avg fraction of top-3 results that are relevant)
    - Fallback rate ≤ 15% (achievable after CP12-13)
    - Latency < 5s single-pass, < 15s agent multi-step — **requires cloud LLM** (local Mistral ~33s, not viable)
    - LLM: **GPT-4o-mini** (OpenAI cloud API, ~$0.0001/query, <2s latency)

> Keep this lightweight. The goal is a reference point, not a bureaucratic artifact.
> If it takes more than one evening, you are over-engineering it.

---

# Phase 1: Scale the Data

*The foundation (Phase 0) was built on 6 pages. Now we have 20,000+ raw files.
Filtering, processing, and re-evaluating at scale is required before any further work.*

---

## Checkpoint 8: Web Crawler (AI)

**Status: DONE**

Recursive web crawler that discovered and downloaded content from all 6 PMF domains.

Crawl results (2026-03-12):
- pmf_uns: 2,736 HTML, 6,794 PDF, 364 docs
- dmi: 898 HTML, 552 PDF
- df: 292 HTML, 1,423 PDF
- dh: 1,243 HTML, 398 PDF
- dbe: 1,525 HTML, 484 PDF
- dgt: 1,649 HTML, 2,150 PDF
- **Total: ~8,343 HTML, ~11,800 PDF** (far exceeds 500+ target)

- [x] Recursive web crawler with link discovery on the same domain:
  - [x] Start from seed URLs in `config.yaml`
  - [x] Extract all `<a href>` links from each page
  - [x] Filter: only follow links within the same domain
  - [x] Normalize URLs: strip fragments (`#section`), resolve relative paths
  - [ ] Lowercase URL normalization (minor — no duplicates observed in practice)
- [x] Configurable `max_pages` per source
- [ ] Configurable `max_depth` (not implemented — `max_pages` is sufficient in practice)
- [x] Politeness:
  - [x] Configurable delay between requests
  - [x] Parse and respect `robots.txt` (custom parser — not `urllib.robotparser`)
  - [x] Descriptive `User-Agent` header
- [x] URL normalization and deduplication (canonicalize before queue insert)
- [x] Expand sources: 6 PMF departments crawled, PDF and Office docs downloaded
- [x] Target: 500+ pages — **exceeded by 16x**
- [ ] **Optional future source — UNS central site (`uns.ac.rs`)**:
  - Contains general study regulations, credit transfer rules, and mobility procedures
  - **Do not crawl yet** — evaluate first whether the 6 existing domains already cover these topics
  - Add only if retrieval eval shows clear gaps that UNS central data would fill

> **AI Note:** Data quality and quantity are the biggest levers in any AI system.
> The crawler has delivered the data. Now the question shifts: does retrieval quality
> hold at 8,000+ pages vs. 6?

---

## Checkpoint 9: Dataset Filtering & Categorization

**Status: IN PROGRESS**

CP1-6 worked on 6 hand-picked pages. 20,000 raw files contain significant noise that
will degrade retrieval if indexed blindly. Filtering is **required before** running the
pipeline at scale.

- [x] **HTML filtering:** (`transform/filter/filter_html.py`)
  - Discard pages with less than N words of useful text (navigation-only, empty pages)
  - Discard error pages (404, "stranica nije pronađena", redirect pages)
  - Discard duplicate content (same text, different URL — common on university sites)
  - Filter report with counts per reason per domain
- [x] **PDF filtering:** (`transform/filter/filter_pdf.py`)
  - Discard empty/corrupted PDFs (0 bytes, unreadable by PyMuPDF)
  - Discard very large PDFs (500+ pages — likely textbooks or theses, not student info)
  - Discard PDFs with no extractable text (scanned images without OCR)
- [x] **Procurement filter:** (`transform/filter/filter_procurement.py`)
  - Keyword-based detection of public procurement PDFs (ćirilica + latinica)
  - ~23% of pmf_uns PDFs are procurement docs — irrelevant for student queries
  - Applied as post-filter on PDF results in orchestrator
- [x] **Deduplication:** (SHA-256 hash in filter orchestrator `transform/filter/run.py`)
  - Hash cleaned text content (SHA-256) to detect exact duplicates across URLs
- [x] **Data analysis:** (`data/analysis/`)
  - Sampled 300 random files proportionally across domains and types
  - LLM categorized into 19 natural categories (bottom-up, not predefined)
  - Decision: index everything except `public_procurement` into vector DB
  - Predefined category tagging deferred — not needed for initial RAG quality;
    can be added later as tool routing (CP13) or metadata filtering (CP19) if eval shows need
- [x] **Transform pipeline:** (`transform/run.py`)
  - Filter orchestrator returns kept files with clean text (`filter/run.py` → `list[KeptFile]`)
  - Save processed files as structured JSON to `data/processed/` (`transform/save_processed.py`)
  - Each JSON contains: clean text, domain, file type, original URL, text hash
- [x] **Chunking:** (`transform/chunker.py`)
  - Split processed text into retrieval-ready chunks
  - Chunk size and overlap from `config/config.yaml`
  - Handle diverse content: academic pages, PDF documents, regulation texts
  - Output: chunked JSON files in `data/chunked/`
- [ ] **Dataset statistics report:**
  - After full run: how many HTML/PDF kept vs discarded, total text size
  - Filter report already logs per-domain/per-reason counts
  - Final numbers pending (full pipeline run in progress)

---

## Checkpoint 10: Embed, Index & Scale Verification

**Status: TODO**

CP9 produces filtered, chunked text. This step embeds it, builds the FAISS index,
and verifies everything works at scale.

- [ ] **Progressive scaling — do NOT run on full dataset immediately:**
  1. Run on ~100 diverse pages (mix of HTML + PDF, all 6 departments) → verify output
  2. Run on ~1,000 pages → check timing, memory, index size
  3. Run on full filtered dataset → final index
- [ ] **Embedding generation:**
  - Run sentence-transformers on all chunks from CP9
  - Verify embedding dimensions and normalization match existing FAISS setup
- [ ] **FAISS index build:**
  - Build index from full chunk set
  - Verify search works (sanity queries)
- [ ] **Scaling checks at each step:**
  - Pipeline runtime (does it finish in reasonable time?)
  - Memory usage (does FAISS index fit in RAM?)
  - Index size on disk
  - Chunk count and avg chunk size (sanity check — no explosion of tiny/empty chunks)

---

## Checkpoint 11: Re-evaluation at Scale (AI)

**Status: TODO**

The most important step in Phase 1. CP4 gave P@1=95% on 6 pages. That number is
meaningless at 20,000 pages — more data means more noise, more competing chunks,
more chances for retrieval to return the wrong thing.

- [ ] Re-run retrieval eval (benchmark.json) on the full index
- [ ] Compare metrics with CP4 baseline:
  - P@1: 95% → ? (expect a drop — the question is how much)
  - MRR: 0.95 → ?
  - FragmentHit@5: 75% → ?
- [ ] Identify failure cases — which queries degraded and why:
  - Is the right chunk in the index but ranked lower? (retrieval problem)
  - Is the right chunk not in the index at all? (filtering/chunking problem)
  - Is there a competing chunk from a similar page? (deduplication problem)
- [ ] Expand benchmark with new questions that cover the scaled dataset
- [ ] **Decision point:** based on eval results, decide priority for Phase 2 and 5:
  - If retrieval degrades badly → prioritize CP19 (better retrieval) or CP20 (better chunking)
  - If retrieval holds → prioritize CP12/CP13 (prompt engineering, tool calling)

> **AI Note:** The 6-page eval was a prototype. The full-dataset eval is the real test.
> More data means more noise and more edge cases. Measure after indexing — do not
> assume quality improved just because more data exists.

---

# Phase 2: Answer Quality

*With the full dataset indexed, focus shifts to what the user actually sees: the
answer. CP12 (eval) and CP13 (optimization) are an iterative loop, not sequential steps.*

---

## Experiment Tracking — A Practice, Not a Checkpoint

From this point on, every change is an experiment. Follow this rule:

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
> Git commits are enough for a solo project with small data.

---

## Checkpoint 12: End-to-End RAG Evaluation (AI)

**Status: TODO** — build baseline BEFORE starting CP13

Retrieval eval (CP4) measures whether the right chunks come back. But that is only
half the story — the actual product is the **final answer**. A system can retrieve
perfect chunks and still produce a wrong answer if the LLM hallucinates, misreads
context, or formats badly. This checkpoint builds the evaluation that measures what
the user actually sees.

**Important:** Build the eval set and measure a baseline BEFORE starting CP13 prompt
changes. Then re-measure after each CP13 experiment. CP12 and CP13 are an iterative
loop: change → measure → decide → repeat.

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
  - This becomes the baseline that all future changes are measured against
- [ ] Add RAG eval to CI (extend CP17):
  - Run end-to-end eval alongside retrieval eval
  - Fail if faithfulness or correctness drops below threshold

> **AI Note:** Retrieval eval tells you "did the system find the right information?"
> RAG eval tells you "did the system give the right answer?" You need both.
> The user does not care about P@1 — they care whether the answer is correct.

---

## Checkpoint 13: Prompt Engineering, Tool Calling & LLM Quality (AI)

**Status: TODO**

The prompt is basic. This is the **highest-ROI improvement** you can make right
now — small prompt changes have outsized impact on answer quality, and the effort
is minimal compared to changing chunking or retrieval architecture.

- [ ] Switch LLM from Ollama/Mistral to **GPT-4o-mini** (OpenAI API):
  - Update `config/config.yaml`: `provider: openai`, `model: gpt-4o-mini`
  - Add OpenAI client in `query/llm_client.py` alongside existing Ollama client
  - Store API key in `.env` (never in config or code)
- [ ] **Tool calling** — LLM decides when and how to search:
  - Define a `search_knowledge_base` tool with OpenAI function calling schema
  - LLM receives the user question and decides: answer directly OR call the tool
  - LLM formulates its own search query (often better than raw user input)
  - If tool is called: execute RAG retrieval, return chunks, LLM generates final answer
  - If tool is not called: LLM responds directly (e.g., "Hvala" → no search needed)
  - This is the foundation for CP15 (Agentic RAG) — learn the mechanic here, expand later
  - Compare quality: tool calling vs. always-search baseline on the eval set
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

# Phase 3: Validate & Extend

*Before investing in tests, CI/CD, and production infrastructure — check if anyone
actually wants this. Then extend with agentic capabilities while tool calling
knowledge from CP13 is fresh.*

---

## Checkpoint 14: Minimal Frontend for User Validation

**Status: TODO**

The system needs real users to validate value. Build the simplest possible interface
and show it to PMF stakeholders.

- [ ] MVP: Streamlit or Gradio app
  - Single text input for the query
  - Display: answer, sources (clickable links), confidence indicator
  - No login, no registration, no session history
- [ ] Show to PMF stakeholders with 20 prepared test questions
- [ ] Collect qualitative feedback:
  - Which answers were helpful?
  - Which were wrong or incomplete?
  - What questions did they try that we didn't anticipate?
- [ ] **Decision point:** based on feedback, decide:
  - Positive → continue to CP15 (Agentic RAG) and beyond
  - Negative → identify what needs to change before further investment

> The feedback from this demo is more valuable than any metric. A ugly app with
> real users beats a polished app with no users.

---

## Checkpoint 15: Agentic RAG (AI)

**Status: TODO**

The current system is single-pass: query -> search -> prompt -> LLM -> answer.
An agentic system can reason, plan, and use tools across multiple steps to
handle complex questions. This is a natural extension of tool calling from CP13 —
same mechanic, but with a loop.

This checkpoint comes *before* the production layer because the agent loop
fundamentally changes the system architecture. An agent makes multiple LLM calls,
multiple searches, and produces a reasoning trace — all of which affect how you design:
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
  - Builds on single-tool calling from CP13 — expand to multi-step reasoning
  - Start with the simplest useful agent: "search, check confidence, re-search if low"
  - This 2-step pattern alone covers a large class of failed queries
- [ ] Multi-step retrieval — agent breaks complex questions into sub-queries:
  - Example: "Uporedi predmete na informatici i matematici" -> two separate searches,
    then combine results
- [ ] Query rewriting — agent reformulates the query if first search returns low-confidence results
- [ ] Expanded tool catalog (building on `search_knowledge_base` from CP13):
  - `search_knowledge_base` — semantic search over indexed chunks (already built in CP13)
  - `lookup_document` — retrieve full document by URL/ID
  - `check_freshness` — verify if source data is current
  - `get_department_contacts` — structured contact lookup
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

# Phase 4: Robustness

*The system works and users confirmed value. Now make it reliable: tests, CI/CD,
and document the architecture that exists.*

---

## Checkpoint 16: Testing

**Status: TODO**

No tests = no confidence in changes. Testing comes now because the pipeline is
stable — CP1 code has been validated at scale (CP10), prompts are tuned (CP13),
and the architecture is unlikely to change drastically.

- [ ] pytest setup with fixtures for config, DB, and test data
  - A shared `conftest.py` with a temporary SQLite database, a small set of test HTML files,
    and a pre-built FAISS index over those files. This is the foundation all tests use.
- [ ] Unit tests for pure functions: chunker (split boundaries, overlap, edge cases),
  HTML cleaner (tag removal, whitespace normalization), prompt builder (template rendering)
  - These are fast, isolated tests. They catch regressions in the most-changed code.
- [ ] Integration tests: run the full pipeline (fetch -> clean -> chunk -> embed -> index)
  on a small set of local test HTML files and verify the output database and index are correct.
  - Use local files, not live URLs — tests must be deterministic and offline.
- [ ] Retrieval regression tests: run the eval set (`data/evaluation/benchmark.json`)
  against the current index and assert that P@1, MRR etc. are above defined thresholds.
  - This is the safety net for Phase 5. If someone changes chunking or retrieval and
    metrics drop, this test fails immediately.
- [ ] Test naming convention: `test_<module>_<behavior>.py` (e.g., `test_chunker_overlap.py`)

> **Why now and not earlier:** Testing a pipeline that's about to change (scaling, new LLM,
> tool calling) means rewriting tests. Now the architecture is stable and tests protect
> real, validated functionality.

---

## Checkpoint 17: CI/CD & Code Quality

**Status: TODO**

CI/CD goes immediately after testing because tests without automation are tests
that stop being run. The goal: every push to the repo is automatically validated,
and no broken code reaches the main branch.

- [ ] GitHub Actions workflow: on every push and pull request, run:
  1. `ruff check` — linting (catches style issues, unused imports, common bugs)
  2. `mypy` — type checking (optional strictness, but at least check public interfaces)
  3. `pytest` — all unit and integration tests from CP16
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

## Checkpoint 18: Architecture Diagrams

**Status: TODO**

Now that the system is stable (pipeline scaled, LLM integrated, tool calling working,
agent loop built), document the architecture that actually exists.

- [ ] Architecture diagrams (simple box-and-arrow, Mermaid or draw.io):
  - System context: the system as a black box with external actors (users, PMF website, LLM, storage)
  - Component diagram: ETL, vector store, retrieval, RAG orchestrator, tool calling, agent loop, config
  - Store in `docs/architecture/` and reference from SPEC
  - **Update these as the system evolves** — they are living documents, not upfront design

---

# Phase 5: Optimization

*Conditional phase — only do what eval results (CP11, CP12) say is needed.
If retrieval and answer quality are already good enough, skip to Phase 6.*

---

## Checkpoint 19: Advanced Retrieval & Embeddings (AI) — conditional

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
> the standard architecture in industry.

---

## Checkpoint 20: Advanced Chunking (AI) — conditional

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

---

# Phase 6: Production

*The system works, users want it, code is tested. Now make it deployable,
safe, and maintainable.*

---

## Checkpoint 21: Incremental Pipeline & Deduplication

**Status: TODO**

The current pipeline drops and recreates the database on every run. For regular
re-crawls in production, this must change — otherwise every crawl re-embeds all
existing content, wasting compute and time.

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
- [ ] Cross-reference crawler with `documents` table to skip already-indexed pages

---

## Checkpoint 22: API Layer & Caching

**Status: TODO**

A CLI is for development. Production systems expose an API. Because the agent (CP15)
is already built, the API handles multi-step responses from the start.

- [ ] FastAPI application with `/ask` endpoint:
  - POST request with `{ "query": "..." }`
  - Response: `{ "answer": "...", "sources": [...], "confidence": "...", "agent_steps": [...], "latency_ms": ... }`
  - Use the Agent pipeline from CP15 as the backend
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
- [ ] CORS configuration for the frontend domain (CP27)

---

## Checkpoint 23: Safety & Guardrails (AI)

**Status: TODO**

A RAG system that anyone can query must handle adversarial input, hallucinations,
and data leakage. With the agent loop (CP15), each agent step is a potential
attack surface.

- [ ] Prompt injection protection:
  - Approach 1: keyword/pattern blocklist for common injection phrases
  - Approach 2: sandwich defense — repeat system instructions after user input
  - **Agent-specific**: run injection checks on the initial query AND on intermediate
    content the agent processes (retrieved chunks could contain injection attempts)
  - Start with 1 + 2, add LLM-based classification if needed
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

## Checkpoint 24: Containerization & Deployment

**Status: TODO**

Making the system runnable anywhere, not just on your machine.

- [ ] **Deployment diagram** — draw how the system runs in production:
  - Containers, networking, volumes, ports, health checks
  - Store in `docs/architecture/`
- [ ] Dockerfile for the application:
  - Multi-stage build: build stage (install dependencies) + runtime stage (slim image)
  - Pin Python version, use `.dockerignore`
- [ ] Docker Compose with app + dependencies:
  - `docker compose up` starts the entire system
  - Internal networking between components
- [ ] Environment-based configuration (dev / prod):
  - Dev: debug logging, no rate limiting
  - Prod: info logging, rate limiting, health checks active
- [ ] Volume mounts for persistent data (SQLite, FAISS index)
- [ ] Health checks + restart policy (`restart: unless-stopped`)
- [ ] README with deployment instructions

---

## Checkpoint 25: Backup & Recovery

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

## Checkpoint 26: Production Monitoring & Drift Detection (AI)

**Status: TODO**

AI systems degrade *silently* — no errors, no crashes, just gradually worse answers.
With the agent loop (CP15), monitoring tracks multi-step execution, not just
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

## Checkpoint 27: Full Frontend & User Feedback

**Status: TODO**

Expand the minimal frontend (CP14) into a full user experience with feedback
collection — the most important data source for system improvement.

- [ ] Expand Streamlit/Gradio app:
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

> **Note:** The feedback mechanism is more important than the UI polish. A ugly app
> with feedback improves; a beautiful app without feedback stagnates.

---

## Summary

| Phase | CP | Topic | Status |
|-------|----|-------|--------|
| **0** | 1 | Core Data Pipeline | DONE |
| **0** | 2 | Pipeline Observability | DONE |
| **0** | 3 | Retrieval Engine | DONE |
| **0** | 4 | Retrieval Evaluation (AI) | DONE |
| **0** | 5 | RAG Layer (AI) | DONE |
| **0** | 6 | Query Observability (AI) | DONE |
| **0** | 7 | System Specification | DONE |
| **1** | 8 | Web Crawler (AI) | DONE |
| **1** | 9 | Dataset Filtering & Categorization | IN PROGRESS |
| **1** | 10 | Pipeline on Scaled Dataset | TODO |
| **1** | 11 | Re-evaluation at Scale (AI) | TODO |
| **2** | 12 | E2E RAG Evaluation — baseline first (AI) | TODO |
| **2** | 13 | Prompt Engineering, Tool Calling & LLM (AI) | TODO |
| **3** | 14 | Minimal Frontend for User Validation | TODO |
| **3** | 15 | Agentic RAG (AI) | TODO |
| **4** | 16 | Testing | TODO |
| **4** | 17 | CI/CD & Code Quality | TODO |
| **4** | 18 | Architecture Diagrams | TODO |
| **5** | 19 | Advanced Retrieval & Embeddings (AI) — conditional | TODO |
| **5** | 20 | Advanced Chunking (AI) — conditional | TODO |
| **6** | 21 | Incremental Pipeline & Deduplication | TODO |
| **6** | 22 | API Layer & Caching | TODO |
| **6** | 23 | Safety & Guardrails (AI) | TODO |
| **6** | 24 | Containerization & Deployment | TODO |
| **6** | 25 | Backup & Recovery | TODO |
| **6** | 26 | Production Monitoring & Drift (AI) | TODO |
| **6** | 27 | Full Frontend & User Feedback | TODO |

**Current progress: Phase 0 complete (CP1-7). CP8 done. CP9 in progress (filtering done, full run pending, chunking next).**

Checkpoints marked with **(AI)** are competencies that separate an AI engineer from a
software engineer who uses AI libraries. They require experimentation, measurement, and
an understanding of why things work — not just how to call the API.
