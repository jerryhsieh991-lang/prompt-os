# prompt-os website (`build_site.py` -> `site/`)

A static, dependency-free educational website generated **from the loop library itself**
(`loops/*.md`). It presents the 154 loop prompts across 26 families as a browsable,
searchable, teachable site.

## Build & run

```bash
python3 build_site.py
cd site && python3 -m http.server 8199
# open http://127.0.0.1:8199/
```

The generator currently writes 218 HTML pages, plus `data/prompts.json`, `sitemap.xml`,
`robots.txt`, `assets/style.css`, and `assets/app.js`. `site/` is generated output:
re-run `build_site.py` after editing any `loops/*.md`; the site stays in sync with the
source of truth. Nothing is hand-written per prompt.

## What's on it

| Route | What |
|-------|------|
| `index.html` | Home - hero, a live color-coded anatomy of one real prompt, starter set, family grid, and corpus stats. |
| `find.html` | Natural-language prompt finder over the full corpus. |
| `library.html` | All 154 prompts. Client-side search + filters (family, verifier type, model tier, starter). No server. |
| `patterns.html` | Pattern index and counts for recurring loop mechanisms. |
| `pattern/<key>.html` | 15 pattern detail pages with matching prompts. |
| `graph.html` | Interactive prompt constellation graph. |
| `loops.html` | Interactive loop visualizer and loop-exit explainer. |
| `automation.html` | Automation pattern library index. |
| `automation/<key>.html` | 12 automation detail pages with flow/run controls. |
| `families.html` | Index of all 26 loop families. |
| `family/<key>.html` | 26 family pages with prompts and curation notes. |
| `anatomy.html` | Universal loop anatomy: components, principles, and antipatterns parsed from the principles doc. |
| `evolve.html` | Evolution stepper showing how prompts become more reliable. |
| `glossary.html` | Glossary of loop-engineering terms. |
| `prompt/<id>.html` | 154 prompt detail pages. Tabs: Prompt, Anatomy, Why it works, Source. |

## How it works

- **Parser** reads each `loops/<family>.md` into structured records (`When/Loop/Stop/Model` +
  the fenced prompt body). Stop conditions are anchor-sliced into the 4 arms
  (`SUCCESS/BUDGET/NO-PROGRESS/BLOCKED`).
- **Anatomy engine** segments each prompt by anchor labels (`GOAL`, `VERIFIER`, action,
  carry-forward state, stop arms), so both blank-line and dense prompts decompose.
- **Facets** are derived signals: verifier type, model-tier hint, length, starter membership,
  and recurring patterns. There is deliberately no fabricated quality score.
- Output is static HTML + CSS + JS only: no tracking, no external requests, and deployable to
  GitHub Pages under the `/prompt-os/` subpath with relative internal links.

## Provenance

All content originates from this repository's loop library, generated through multi-agent
authoring with adversarial verification and human review. The site preserves that provenance on
every prompt's **Source** tab; it does not claim ownership or present reconstructions as originals.

<!-- Counts verified 2026-07-19 from `python3 build_site.py`: 154 prompts, 26 families, 218 HTML pages. -->
