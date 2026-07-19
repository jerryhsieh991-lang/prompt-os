# prompt-os website (`build_site.py` -> `site/`)

A static, dependency-free educational website generated **from the loop library itself**
(`loops/*.md`). It presents the 170 loop prompts across 32 families as a browsable,
searchable, teachable site.

## Build & run

```bash
python3 build_site.py
cd site && python3 -m http.server 8199
# open http://127.0.0.1:8199/
```

The generator currently writes 243 HTML pages, plus `data/prompts.json`, `sitemap.xml`,
`robots.txt`, `assets/style.css`, and `assets/app.js`. `site/` is generated output:
re-run `build_site.py` after editing any `loops/*.md`; the site stays in sync with the
source of truth. Nothing is hand-written per prompt.

## What's on it

| Route | What |
|-------|------|
| `index.html` | Home - hero, a live color-coded anatomy of one real prompt, starter set, family grid, and corpus stats. |
| `find.html` | Natural-language prompt finder over the full corpus. |
| `lab.html` | Paste your own prompt; the same client-side engine analyzes its anatomy, patterns, verifier, complexity, and flags missing loop structure. |
| `learn.html` | Grounded micro-course + quizzes on loop engineering, drawn from the library's own principles; progress saved client-side. |
| `compare.html` | Two prompts side by side — shared vs unique patterns, verifier, complexity, exits, anatomy. Pick from the library or paste your own. |
| `library.html` | All 170 prompts. Client-side search + filters (family, verifier type, model tier, starter). No server. |
| `patterns.html` | Pattern index and counts for recurring loop mechanisms. |
| `pattern/<key>.html` | 15 pattern detail pages with matching prompts. |
| `graph.html` | Interactive prompt constellation graph. |
| `loops.html` | Interactive loop visualizer and loop-exit explainer. |
| `automation.html` | Automation pattern library index. |
| `automation/<key>.html` | 12 automation detail pages with flow/run controls. |
| `families.html` | Index of all 32 loop families. |
| `family/<key>.html` | 32 family pages with prompts and curation notes. |
| `anatomy.html` | Universal loop anatomy: components, principles, and antipatterns parsed from the principles doc. |
| `evolve.html` | Evolution stepper showing how prompts become more reliable. |
| `glossary.html` | Glossary of loop-engineering terms. |
| `prompt/<id>.html` | 170 prompt detail pages. Tabs: Prompt, Anatomy, Why it works, Source. |

## How it works

- **Parser** reads each `loops/<family>.md` into structured records (`When/Loop/Stop/Model` +
  the fenced prompt body). Stop conditions are anchor-sliced into the 4 arms
  (`SUCCESS/BUDGET/NO-PROGRESS/BLOCKED`).
- **Anatomy engine** segments each prompt by anchor labels (`GOAL`, `VERIFIER`, action,
  carry-forward state, stop arms), so both blank-line and dense prompts decompose.
- **Facets** are derived signals: verifier type, model-tier hint, length, starter membership,
  and recurring patterns. There is deliberately no fabricated quality score.
- The **home hero** is a dark deep-space band with a real-time 3D loop rendered in **raw WebGL**
  (zero dependencies, no Three.js). On load the ring **assembles from scattered particles** (formation,
  easeOutCubic); then it rotates slowly (~24s/rev) with a warm-ember **comet** orbiting it, an ambient
  dust field (cool + violet + a few ember motes), per-node breathing, and a **cursor-parallax tilt**
  (lerp 0.07). Palette is a matched indigo->violet gradient + cyan->violet glow ramp with a terracotta
  ember accent that ties the cool hero to the warm body. It pauses when offscreen/hidden and falls back
  to a static SVG ring for reduced-motion / no-WebGL / no-JS. The rest of the site keeps its warm theme.
- Output is static HTML + CSS + JS only: no tracking, no external requests, and deployable to
  GitHub Pages under the `/prompt-os/` subpath with relative internal links.

## Provenance

All content originates from this repository's loop library, generated through multi-agent
authoring with adversarial verification and human review. The site preserves that provenance on
every prompt's **Source** tab; it does not claim ownership or present reconstructions as originals.

<!-- Counts verified 2026-07-19 from `python3 build_site.py`: 170 prompts, 32 families, 243 HTML pages (incl. /lab and /compare). -->

## Client-side analysis engine (`/lab` and `/compare`)

The deterministic analysis engine (anatomy segmentation, pattern detection, verifier
classification) lives in Python in `build_site.py`. So `/lab` and `/compare` can run it on
*arbitrary pasted text* in the browser without a second, drifting copy, `analysis_rules()`
serializes the engine's rule tables (anchors, verifier keyword lists, pattern metadata) into
`app.js` at build time (`window.PROMPTOS_RULES`); a compact JS mirror consumes them. A
build-time browser check confirms **exact parity**: for all 170 corpus prompts the JS engine
produces the identical verifier type and pattern set as the Python build.
