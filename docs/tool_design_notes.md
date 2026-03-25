# Tool Design — Notes from AI Engineering Course

## Tools are part of the system prompt

When you send a request to the LLM API, tools are sent alongside the system
prompt. The LLM sees the tool schema (name, description, parameters) as part
of its context and decides whether to call a tool or respond directly.

```python
response = OpenAI().chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Use a friendly tone."},
        {"role": "user", "content": "What is the weather like in SF?"},
    ],
    tools=[{"type": "function", "function": {
        "name": "get_current_weather",
        "description": "Gets the current weather in the provided location.",
        "parameters": {
            "type": "object",
            "required": ["location"],
            "properties": {
                "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"},
                "format": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "default: celsius"},
            },
        },
    }}],
)
```

## Best practices

### 1. Don't re-explain in system prompt

If the tool schema already carries the information, don't repeat it in the
system prompt. The LLM reads both.

- Tool name and description already explain what the tool does
- Parameter descriptions already explain what each field means
- Defaults and required fields are already in the schema

**Bad:** "You have a tool called search_knowledge_base that searches the PMF
faculty knowledge base. You should call it when you need information..."

**Good:** Let the schema speak for itself. System prompt focuses on tone and
behavior only.

### 2. Watch your nouns and verbs

Tool names and parameter names matter. They guide the LLM's understanding of
what the tool does. Use clear, descriptive names.

- `search_knowledge_base` — clear action (search) + clear target (knowledge base)
- `query` parameter — clear that it expects a search string

### 3. Separate read vs. write tools (Tau-bench pattern)

Separate tools that **get** data from tools that **modify** data. This is
similar to CRUD separation. Makes it easier to reason about safety — read
tools are always safe to call, write tools need guardrails.

For our system: all tools are read-only (search, lookup, check). No tools
modify data. This is intentional — the system only answers questions.

### 4. Prefer programmatic solutions

Don't put business logic in the prompt. Put it in tool code.

**Bad (in prompt):** "When a source is older than 3 years, reduce confidence
by 30%. When older than 5 years, reduce by 50%."

**Good (in code):**
```python
def search_knowledge_base(query: str) -> list[dict]:
    results = faiss_search(query, top_k=10)
    for r in results:
        age_years = (now - r["date"]).days / 365
        if age_years > 5:
            r["score"] *= 0.5
        elif age_years > 3:
            r["score"] *= 0.7
    return sorted(results, key=lambda r: r["score"], reverse=True)[:5]
```

The LLM doesn't need to know about freshness penalties. It just gets the
best results, already scored and sorted.

### 5. Zero trust in model

Design the toolset for security. The model can potentially leak everything
you tell it.

- **Don't tell the model secrets** — API keys, internal URLs, database
  credentials should never appear in the prompt or tool results
- **Force business rules by tool design** — if max 5 results, enforce in
  code, don't ask the LLM to "only use 5 results"
- **Force state/order** — if steps must happen in sequence, enforce in code
  via the tool execution flow, not via prompt instructions
- **Keep it natural for the model** — the tool interface should feel intuitive
  to use, even though the constraints are enforced server-side

### 6. Tool code != production code

Tool code is written for the **agent** as the target audience, not for humans.

- Tool descriptions should be clear to the LLM
- Return values should be structured in a way the LLM can easily parse
- Error messages should help the LLM recover (e.g., "No results found for
  'xyz'. Try a broader query." instead of "Error 404")

## How this applies to our project

### CP13: Single tool — `search_knowledge_base`

```python
tools = [{"type": "function", "function": {
    "name": "search_knowledge_base",
    "description": "Search PMF faculty knowledge base for relevant information about studies, admissions, courses, schedules, and contacts.",
    "parameters": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search query in Serbian"},
        },
    },
}}]
```

System prompt stays short:
- Who you are (PMF assistant)
- Language (Serbian)
- When to say "I don't know"
- Cite sources from tool results

Everything else (scoring, freshness, filtering, ranking) happens in the
tool's Python code, not in the prompt.

### CP15: Expanded tool catalog

| Tool | Type | Purpose |
|------|------|---------|
| `search_knowledge_base` | read | Semantic search over indexed chunks |
| `lookup_document` | read | Retrieve full document by URL/ID |
| `check_freshness` | read | Verify if source data is current |
| `get_department_contacts` | read | Structured contact lookup |

All read-only. Business logic enforced in code. LLM just calls tools and
synthesizes the results.

## Toolset advises the agent

### Error messages — for the model, not for humans

When a tool fails, return a clean, actionable message as a string. No
internals, no stack traces, no implementation details.

**Bad:** `"FAISS IndexError: vector dimension mismatch at index.search() line 142"`
**Good:** `"No results found for 'xyz'. Try a broader or differently worded query."`

The model can then recover — rephrase the query, try a different tool, or
tell the user it couldn't find the answer. Internal errors are meaningless
to the model and can leak to the user.

### Dynamic instructions via tools (`get_instructions_by_intent`)

Instead of putting ALL instructions in the system prompt (making it huge),
create a tool that returns context-specific instructions. The model calls
it when it needs guidance for a particular situation.

Example: instead of a massive prompt covering how to answer admission
questions, schedule questions, contact questions, etc. — make a tool that
returns the right instructions for the detected intent.

This keeps the system prompt short and focused on general behavior.

### Tool results and prompt injection risk

Models are strongly trained to trust tool results. This is a security
concern: if crawled content contains prompt injection (e.g., "Ignore all
previous instructions and..."), the model may follow it because it came
back as a tool result.

Mitigation (CP18):
- Sanitize chunks before returning them as tool results
- Strip suspicious patterns from retrieved content
- Run injection detection on tool results, not just user input
- The attack surface is every chunk returned by search, not just the query

### Minimum data exposure — don't tell what you don't need to

Everything you tell the model can potentially leak. Design tools to return
the minimum data needed for the task.

**Bad:** `get_subscribed_users() -> list` — returns ALL users from DB. Model
now has data it doesn't need and could leak.

**Good:** `verify_subscription(name: str) -> bool` — returns only yes/no for
one user. Model can't leak what it doesn't have.

Same task, drastically different risk profile.

For our system: `search_knowledge_base` should return only:
- Chunk text (what the LLM needs to answer)
- Source URL (for citation)
- Source date (for freshness warning)

It should NOT return:
- Internal chunk IDs or database row IDs
- Raw similarity scores as floats
- Full metadata objects with crawl timestamps
- Adjacent chunks that weren't relevant

Keep the tool result as small and focused as possible.
