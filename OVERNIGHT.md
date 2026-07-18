# Overnight autonomous run — 2026-07-18

**What's running:** bounded, gated corpus expansion while you're away. Each batch authors
new agent-loop families, adversarially verifies them (author → verify → repair), and only
**verified, clean-building** batches get committed + deployed. Data-only changes flow through
the existing analysis engine (proven safe across 3 rounds earlier tonight).

## Guardrails (chosen because you were asleep — no runaway, no broken live site)
- **Bounded:** cap ~3 batches total. Stop early if a batch yields < 2 verified prompts
  (returns are already diminishing: +7 → +10 → +4) or on repeated failure.
- **Gated deploys:** a batch is committed/deployed to `main` (→ live) only if `build_site.py`
  builds clean AND the prompt count grew AND there are 0 empty/broken prompts. A bad batch is
  discarded, not shipped — the live site can't be broken by a failed round.
- **Robustness:** families are now auto-discovered from `loops/*.md` — a new family needs no
  code edit, so an automated round can't corrupt `build_site.py`.
- **Out of scope for unattended work:** Phase-5 interactive JS (constellation graph, prompt
  evolution, page transitions). Building complex JS unattended and auto-deploying to a live
  public site is too risky — those are for an attended session.

## Progress log
- **Start:** 133 prompts / 20 families, live at https://jerryhsieh991-lang.github.io/prompt-os/
- **Batch 1 done:** structured-extraction / agent-memory / video-generation. **Hit the account SESSION
  LIMIT mid-run (resets 1am PT)** — most repair/reverify agents failed on the limit, so yield was low:
  **+3 verified** (agent-memory 2, video-generation 1; structured-extraction 0). Integrated → **136 prompts / 22 families**.
- **Phase-5 shipped:** built the **Prompt Constellation graph** (`/graph`) — 136 nodes clustered by family,
  440 real edges (curation near-dups + shared patterns), hover-highlight / click-to-open / family filter,
  keyboard-accessible, no-JS fallback list. Runtime-verified (0 console errors, all interactions work, no overflow).
- **Blocked on more corpus:** the session limit means launching more authoring workflows will just fail.
  Per the "don't grind failures" rule, I stopped launching batches and scheduled a resume for after the
  1am PT reset (see cron/wakeup). Everything above is committed + deployed and gated (live site verified).
- **Still deferred (attended):** prompt-evolution diff page, page transitions — didn't get to them before the limit.
