# prompt-os

A small, opinionated toolkit for **agent loops** — the prompts and the one agent that turn a task
into a reliable, self-terminating loop instead of a one-shot guess.

Three parts, nothing more:

| Folder | What it is |
|--------|------------|
| **[loops/](loops/)** | A library of **182 reusable loop prompts** across 38 loop families (build→verify, debug, red-team, refactor, research-until-dry, migration, eval, orchestration, extraction, incident response, API integration, …). Each is copy-pasteable, model-agnostic, and has an explicit stop condition so an agent can't loop forever. Start at [loops/README.md](loops/README.md). |
| **[agents/prompt-loop-engineer.md](agents/prompt-loop-engineer.md)** | One bounded agent: given a task it classifies the loop, writes the loop prompt, specifies the harness (stop conditions, fan-out, anti-runaway guard), and emits a ready-to-run spec. |
| **[research/fable-5-usage.md](research/fable-5-usage.md)** | Multi-agent, adversarially-verified research on how people actually use Claude Fable 5 — feeds the agent's model-routing decisions (only 6/12 headline claims survived verification; the report says which). |

## Design stance

- **A loop is:** a frozen goal + one action per turn + an explicit stop condition + a verifier that
  closes each turn. Every prompt here has all four. See
  [loop-engineering principles](loops/00-loop-engineering-principles.md).
- **Stop conditions are non-negotiable.** Every prompt terminates on the first of
  `SUCCESS` / `BUDGET` / `NO-PROGRESS` / `BLOCKED` — never "until it looks done".
- **Powerful = well-bounded, not big.** The agent emits *one* loop spec for the task asked. No
  runtime, no daemon, no "does everything". That restraint is the point.

## Use it

- Browse [loops/](loops/), copy the prompt that fits, fill the `<PLACEHOLDERS>`, run it.
- Or hand a task to the **prompt-loop-engineer** agent and let it compose the loop for you.
  Register it as a Claude Code skill by copying it into `~/.claude/skills/`.

## Website

The library is also a browsable, searchable, teachable **static site** — Home → Library →
Prompt detail → Anatomy — generated straight from `loops/*.md`. Build with
`python3 build_site.py`, then serve `site/`. See **[SITE.md](SITE.md)**.

## Build & verify

```bash
python3 build_site.py          # writes site/ (fails loudly on a corrupt corpus)
node tools/check_js.mjs        # Python/JS analysis-engine parity across the corpus
python3 tools/regen_index.py   # regenerate loops/README.md from loops/*.md
python3 test_build.py          # generator + regression self-checks
```

The build **fails** rather than warns on an empty prompt body, a missing stop arm, an
unresolvable starter entry, or a page/sitemap mismatch; it writes to a staging directory
and swaps only on success, so a failed build cannot damage the published site. Output is
byte-for-byte deterministic. Set `PROMPT_OS_BASE_URL` to your own origin when deploying a
fork — it defaults to `http://localhost:8199/` so a fork can never emit canonical URLs
pointing at someone else's deployment.

## Provenance

The library and research were generated through multi-agent authoring with adversarial verification
and then human-reviewed. Regenerate/extend by editing the loop families and re-running the same
pipeline.

<!-- Counts are generated: loops/README.md is produced by tools/regen_index.py and
     CI fails if it drifts from loops/*.md. -->
