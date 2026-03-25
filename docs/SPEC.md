# System Specification

## 1. Goal

AI assistant that answers questions about studying at the Faculty of Sciences
(PMF), University of Novi Sad. Uses RAG (retrieval-augmented generation) over
crawled faculty web pages and documents.

## 2. Target Users

### Prospective students (high schoolers)
- Admission requirements, entrance exams, available programs
- "Da li postoji prijemni ispit?", "Koliko traju osnovne studije?"

### Master/PhD candidates
- Entry requirements, program duration, available specializations
- "Mogu li na master informatike sa drugog fakulteta?"

### Current students (especially 1st year)
- Exam registration, schedules, ESPB requirements, admin procedures
- "Kako se prijavljuje ispit?", "Koliko ESPB treba za godinu?"

## 3. Data Scope

### Crawled domains (BFS crawler)

Full-site BFS crawl of all publicly available pages, PDF files, and Office
documents. Each domain is stored in `data/raw/{name}/` with subfolders
`html/`, `pdf/`, `docs/` and a `metadata.json` mapping filenames to source
URLs, content types, and timestamps.

| Name | Domain | Purpose | Content types |
|------|--------|---------|---------------|
| pmf_uns | www.pmf.uns.ac.rs | general_info | HTML, PDF, Office docs |
| dmi | www.dmi.uns.ac.rs | department_info | HTML, PDF, Office docs |
| df | www.df.uns.ac.rs | department_info | HTML, PDF, Office docs |
| dh | www.dh.uns.ac.rs | department_info | HTML, PDF, Office docs |
| dbe | wwwold.dbe.pmf.uns.ac.rs | department_info | HTML, PDF, Office docs |
| dgt | www.dgt.uns.ac.rs | department_info | HTML, PDF, Office docs |

Sitemap estimate for pmf_uns: ~1427 HTML pages. Actual crawl yields
significantly more due to pages not listed in sitemap (archived news,
pagination, linked PDFs and documents).

### Content types collected
- **HTML** — web pages (news, program descriptions, staff pages, regulations)
- **PDF** — regulations, curricula, exam schedules, reports, forms
- **Office docs** — .doc, .docx, .xls, .xlsx, .ppt, .pptx (syllabi, templates, schedules)

### Metadata tracking

Each domain's `metadata.json` stores per-file:
- `url` — original source URL (used for R2 source links in responses)
- `content_type` — HTTP Content-Type header
- `last_modified` — HTTP Last-Modified header (used for R4 source date, R6 freshness)
- `file_type` — html, pdf, doc, docx, xls, xlsx, ppt, pptx
- `crawled_at` — UTC timestamp of download
- `content_length` — file size in bytes

### Out of scope (data)
- Internal systems (e-Student, Moodle) — require login
- Personal data (student records, grades)
- Other UNS faculties (FTN, Pravni, Medicinski...)
- Social media content (Reddit, forums)
- Content in languages other than Serbian

## 4. Knowledge Domains

| # | Domain | Example topics |
|---|--------|---------------|
| 1 | Admissions | Requirements, entrance exam, quotas, ranking, documents |
| 2 | Study programs | Bachelor, master, PhD programs per department |
| 3 | Courses | Course lists, descriptions, ESPB credits, year/semester |
| 4 | Teaching | Schedules, professors, assistants, materials |
| 5 | Administration | Student office, exam registration, deadlines, regulations |
| 6 | Finances | Tuition, scholarships, budget vs. self-funded |
| 7 | Student life | Organizations, internships, exchanges, competitions |

## 5. Benchmark Questions

The system must answer these correctly. Used for regression testing.

### Admissions
1. Da li postoji prijemni ispit na PMF?
2. Koliko studenata se prima na informatiku?
3. Ko je oslobođen polaganja prijemnog ispita?
4. Koliko bodova je potrebno da se položi prijemni iz fizike?

### Study programs
5. Koji studijski programi postoje na Departmanu za matematiku?
6. Koliko traju osnovne studije informatike?
7. Postoji li master iz Data Science na PMF-u?
8. Ko je rukovodilac studijskog programa matematike?

### Courses & teaching
9. Šta je dozvoljeno koristiti na prijemnom ispitu iz fizike?
10. Koji su predmeti na prvoj godini informatike?

### Administration & contact
11. Koji je email za upis na informatiku?
12. Kada je dodatni januarski ispitni rok?

### News & events
13. Šta je akcija "Budi student jedan dan"?
14. Koji tim je učestvovao na Serbian Cybersecurity Challenge?
15. Gde su studenti informatike bili na zimskoj školi?

## 6. Quality Targets

### Current baseline (CP12, full dataset, 83k chunks, GPT-4o-mini)

| Metric | Value |
|--------|-------|
| Answer correctness (avg) | 2.47 / 3.0 |
| Answer pass rate (C=3) | 58.3% |
| Faithfulness (avg) | 2.18 / 3.0 |
| LLM latency (GPT-4o-mini) | < 2s |
| Total latency | ~4–6s |

*Earlier retrieval-only baseline (CP4/CP6, 6 pages): P@1=95%, MRR=0.95 — obsolete after full-scale index.*

### Production targets (after CP11-14)

| Metric | Target | Notes |
|--------|--------|-------|
| P@1 | >= 90% | Strict: is top-1 result relevant? May drop at scale, then recover |
| Precision@3 | >= 80% | Strict: avg fraction of top-3 results that are relevant |
| MRR | >= 0.90 | |
| Fallback rate | <= 15% | For in-scope questions, achievable after CP12-15 |
| Answer correctness | >= 80% | Measured by CP13 eval |
| Answer faithfulness | >= 95% | No hallucination |
| Total latency | < 10s | Requires cloud or GPU LLM — local Mistral 7B is ~33s, not viable |

**LLM: GPT-4o-mini** (OpenAI cloud API) — ~$0.0001/query, <2s latency.

## 7. Functional Requirements — Query Response

Every response to a user query MUST include:

### 7.1 Core (mandatory)
| # | Field | Description |
|---|-------|-------------|
| R1 | **Answer** | Generated text answering the user's question |
| R2 | **Source links** | Direct URL(s) to the page/document the answer is based on |
| R3 | **Relevance score** | Confidence percentage (e.g. 87%) indicating how sure the system is |
| R4 | **Source date** | When the source was last updated or created |

### 7.2 Enrichment (highly recommended)
| # | Field | Description |
|---|-------|-------------|
| R5 | **Key facts summary** | Bullet-point extraction of the most important facts from context |
| R6 | **Freshness warning** | Alert when source is older than 2 years: "Information may be outdated" |
| R7 | **Fallback notice** | Clear message when no relevant info is found — never fabricate an answer |
| R8 | **Related questions** | 2-3 suggested follow-up questions the user might ask next |

### 7.3 Additional context
| # | Field | Description |
|---|-------|-------------|
| R9 | **Source type** | Label: web page, PDF document, regulation, etc. |
| R10 | **Department** | Which department the information comes from (DMI, DF, DH, DBE, DGT, PMF central) |
| R11 | **Contact suggestion** | When the question requires a human answer, suggest relevant email/phone |

### 7.4 Recency & relevance policy
- Documents older than 3 years receive a reduced relevance weight (×0.7)
- Documents older than 5 years receive a stronger penalty (×0.5)
- The system always prefers the most recent source when multiple sources contain similar information
- Source date is extracted from: PDF metadata (CreationDate), HTTP Last-Modified header, or page content

## 8. Data Pipeline

```
crawl → transform → chunk → embed → index → query → respond
```

| Stage | Module | Input | Output |
|-------|--------|-------|--------|
| 1. Crawl | `ingest/crawler.py` | Config domains | `data/raw/{domain}/html,pdf,docs/` + `metadata.json` |
| 2. Transform HTML | `transform/html_to_text.py` | Raw HTML files | `data/processed/{domain}__{slug}.json` |
| 3. Transform PDF | `transform/pdf_to_text.py` | Raw PDF files | `data/processed/{domain}__pdf__{slug}.json` |
| 4. Chunk | `chunk/chunker.py` | Processed JSON | `data/chunked/*.json` (400 tokens, 80 overlap) |
| 5. Embed | `embedding/embedder.py` | Chunks | `data/embeddings/faiss_index` |
| 6. Query | `query/retriever.py` | User question | Top-k chunks by cosine similarity |
| 7. Respond | `rag/generator.py` | Chunks + question | Structured response (R1–R11) |

### Tool calling (CP13+)

The LLM does not always search. Instead, it receives a tool definition
(`search_knowledge_base`) and decides per query whether to call it:

```
User question → LLM (with tool schema)
  ├─ LLM calls search_knowledge_base(query="...") → retrieval → chunks → LLM → answer
  └─ LLM answers directly (no search needed, e.g., greetings, clarifications)
```

The LLM formulates its own search query, which is often more precise than the
raw user input. This is the single-tool foundation for the full agent loop (CP16).

### Processed document format

Each transformed document is a JSON file with:
```json
{
  "text": "cleaned plain text content...",
  "metadata": {
    "source": "pmf_uns",
    "purpose": "general_info",
    "raw_filename": "vesti__page__2.html",
    "file_type": "html",
    "processed_at": "2026-03-11T22:15:30+00:00",
    "text_length": 4523
  }
}
```

Source URL is resolved at query time via `metadata.json` in the raw domain
folder, using `raw_filename` as the lookup key.

## 9. Interaction Model

The system is a **single-question academic advisor**, not a chatbot.

### Design principles
- **Stateless** — each query is independent, no conversation history or sessions
- **One question → one comprehensive answer** — no follow-up needed
- **Better than generic AI** — answers are grounded in actual PMF data, not general knowledge
- **Transparent** — every claim is backed by a source link and confidence score

### Response structure

Every response is a structured card with these sections:

```
┌─────────────────────────────────────────────┐
│  ODGOVOR                                     │
│  [Generated answer text in Serbian]          │
│                                              │
│  📊 Pouzdanost: 87%                          │
│                                              │
│  📌 Ključne činjenice:                       │
│  • Fact 1                                    │
│  • Fact 2                                    │
│  • Fact 3                                    │
│                                              │
│  🔗 Izvori:                                  │
│  • pmf.uns.ac.rs/studije/upis (web stranica) │
│  • pravilnik_o_upisu.pdf (PDF, 2025)         │
│                                              │
│  ⚠️ Izvor je stariji od 2 godine             │
│                                              │
│  💡 Slična pitanja:                          │
│  • Koji su rokovi za prijavu?                │
│  • Koliko košta školarina?                   │
│                                              │
│  📧 Za dodatne informacije: upis@pmf.uns... │
└─────────────────────────────────────────────┘
```

This maps directly to functional requirements R1–R11 from Section 7.

### Why not a chatbot
- Students want fast, reliable answers — not a conversation
- Stateless design is simpler, cheaper, and more reliable
- No risk of hallucination compounding across conversation turns
- Every answer stands on its own with full source attribution

## 10. Out of Scope (system behavior)

The system explicitly does NOT:
- Give personalized academic advice ("Should I study CS or math?")
- Access or display personal student data
- Provide legally binding interpretations of regulations
- Answer questions about other UNS faculties
- Handle admission for foreign citizens (specific procedures)
- Translate content to other languages
- Perform calculations (e.g., "Will I pass with these grades?")
