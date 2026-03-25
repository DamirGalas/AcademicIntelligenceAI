# Boilerplate Analysis — PMF Domains

Analysis date: 2026-03-24

## Problem

Nav menus and site headers are included in the extracted text because sites use
`<div>` elements instead of semantic `<nav>`/`<header>` tags. Although `nav`,
`header`, and `footer` are already in `strip_tags`, they have no effect on
these sites.

The boilerplate ends up in chunks and pollutes retrieval — especially on DF
where the first 6–7 chunks of a page are pure navigation text before the actual
article begins.

## Domain-by-domain findings

### www.dh.uns.ac.rs — 844 pages — SEVERE (97%)

97% of pages contain this fixed header block immediately after the page title:

```
Skip to content Prirodno-matematički fakultet Univerziteta u Novom Sadu
DEPARTMAN ZA HEMIJU, BIOHEMIJU I ZAŠTITU ŽIVOTNE SREDINE
+381-21-485-2720 infohemija@dh.uns.ac.rs Envelope Facebook Instagram Tiktok Linkedin-in
```

Confirmed via phrase checks:
- `infohemija@dh.uns.ac.rs` → 97.2%
- `+381-21-485-2720` → 97.2%
- `Envelope Facebook` → 96.6%

### www.dmi.uns.ac.rs — 502 pages — HIGH (95%)

95% of pages contain `Skip to content` immediately after the title suffix
`– Departman za matematiku i informatiku`. After `Skip to content`, the actual
article content begins — so the nav is short but consistent.

Pattern to strip: `– Departman za matematiku i informatiku Skip to content`

### www.df.uns.ac.rs — 307 pages — SEVERE (variable)

The most damaging case. The navigation menu is very long and occupies the
**first 6–7 chunks** of every page before the actual article starts. Example
structure (one page = 9 chunks total, chunks 0–6 are all nav):

```
chunk 0: ... Meni Početak O nama O fakultetu Istorijat departmana Rukovodstvo Katedre ▸ Katedra za eksperimentalnu fiziku ...
chunk 1: ... iziku Katedra za opštu fiziku i metodiku nastave fizike Katedra za radijacionu i subatomsku fiziku ...
...
chunk 7: ... Događaji Konkursi [PAGE TITLE] No Comments [actual article content] ...
chunk 8: ... Kontakt Trg Dositeja Obradovića 4, 21000 Novi Sad 021/485-2800 info@df.uns.ac.rs
```

The nav starts with `– Departman za fiziku Prirodno-matematički fakultet
Univerzitet u Novom Sadu Meni Početak O nama` and ends at `Događaji Konkursi`
followed by the page title appearing a second time.

### wwwold.dbe.pmf.uns.ac.rs — 1347 pages — HIGH (very consistent)

Every page starts with a fixed English navigation block:

```
Department of Biology and Ecology Faculty of Sciences about STUDYING SCIENTIFIC
RESEARCH NEWS NIGHT OF BIOLOGY POPULAR STUFF prijava (odjava) SEARCH
```

Also ends with a fixed footer:
```
Faculty of Sciences, University of Novi Sad Trg Dositeja Obradovića 3, 21000 Novi Sad, Srbija Phone: +381 21 455630
```

### www.pmf.uns.ac.rs — 2220 pages — LOW

Only `Skip to main content` is consistently present. The content after it
varies immediately. Low priority.

### www.dgt.uns.ac.rs — 767 pages — LOW / UNCLEAR

No consistent nav prefix detected. Some pages are in English, some Serbian,
content varies immediately. Nav structure may be different per page type.

## Root cause

`filter_html.py` → `_parse_and_clean()` calls `soup.get_text(separator=" ")`
on the entire DOM. Sites use `<div class="menu">` or similar instead of `<nav>`
so the existing `strip_tags` config has no effect.

## Proposed fix approaches

### Option A: Target main content area (recommended)
In `_parse_and_clean`, prefer `<main>`, `<article>`, or `<div id="content">`
if present, and only fall back to full body if none found. This is clean and
domain-agnostic.

### Option B: Domain-specific strip patterns (text-level)
After text extraction, apply per-domain regex to strip known boilerplate
strings. More fragile but works even when HTML is unstructured.

### Option C: Both
Use Option A as primary (catches well-structured sites), Option B as fallback
for sites that still leak boilerplate.

## Impact estimate

Fixing DH (844 pages × ~97%) and DF (307 pages × 6–7 wasted chunks) alone
could significantly improve retrieval. DBE old (1347 pages) is a bonus.

After fix: full re-embed + re-index required (~83k chunks).

## Confirmed production impact (2026-03-25)

Manual test: query "Koje predmete predaje Petar Mali?" against the live index
revealed the full severity of the DF boilerplate problem.

The page `https://www.df.uns.ac.rs/o-nama/imenik/petar-mali/` has 23 chunks in
the index. The chunk containing "Nastava i kursevi" (course list) is at index
~9. With `max_chunks_per_url=2`, the top-2 FAISS results for this query were
both boilerplate nav chunks — the answer chunk never surfaced.

**Workarounds applied (temporary, to be removed after proper fix):**
- `max_chunks_per_url` increased from 2 → 10 (config)
- Heuristic text filter in `search.py` to skip chunks containing
  `Skip to content`, `▸▸▸`, `Meni Početak`, `Vesti Vesti sa Departmana`,
  `Korisni linkovi Veb servisi`, `UNS dokumenti` + `Vesti`

These workarounds allowed the correct answer to surface, but are fragile and
domain-specific. The real fix remains Option A/C in the transform stage.

Test case added: id=65 "Koje predmete predaje Petar Mali?" (type: factual, dept: df)
