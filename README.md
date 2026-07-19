# prompt-os

A small, opinionated toolkit for **agent loops** — the prompts and the one agent that turn a task
into a reliable, self-terminating loop instead of a one-shot guess.

Three parts, nothing more:

| Folder | What it is |
|--------|------------|
| **[loops/](loops/)** | A library of **158 reusable loop prompts** across 26 loop families (build→verify, debug, red-team, refactor, research-until-dry, migration, eval, orchestration, extraction, incident response, API integration, …). Each is copy-pasteable, model-agnostic, and has an explicit stop condition so an agent can't loop forever. Start at [loops/README.md](loops/README.md). |
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

## Provenance

The library and research were generated through multi-agent authoring with adversarial verification
and then human-reviewed. Regenerate/extend by editing the loop families and re-running the same
pipeline.

<!-- Counts verified 2026-07-19 from `python3 build_site.py`: 158 prompts across 26 families. -->
