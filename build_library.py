#!/usr/bin/env python3
"""Turn the prompt-os-build workflow output into the on-disk library.

Writes: research/fable-5-usage.md, loops/00-loop-engineering-principles.md,
loops/<key>.md (14 category files), loops/README.md (index + starter set).
Category order matches the workflow's pipeline order, so we relabel by index.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = sys.argv[1] if len(sys.argv) > 1 else \
    "/private/tmp/claude-501/-Users-jerryjerry-Projects-tokenizer-training/473865b5-824f-4417-9f21-3d675e157632/tasks/wvqgb2412.output"

data = json.load(open(OUT))
r = data.get("result", data)
fable5, verdicts = r["fable5"], r["verdicts"]
bp, cats, curation = r["best_practices"], r["categories"], r["curation"]

# clean key + human title, in pipeline order
KEYS = [
    ("build-verify", "Build → Verify"),
    ("debug-rootcause", "Debug / Root-Cause"),
    ("redteam-verify", "Red-Team / Adversarial Verify"),
    ("refactor-safe", "Safe Refactor"),
    ("research-until-dry", "Research Until Dry"),
    ("planning-decompose", "Planning / Decompose"),
    ("test-generation", "Test Generation"),
    ("review-dimensions", "Review by Dimensions"),
    ("self-critique", "Self-Critique (Draft → Critique → Revise)"),
    ("migration-codemod", "Migration / Codemod"),
    ("eval-benchmark", "Eval / Benchmark"),
    ("orchestration-harness", "Orchestration Harness (Fan-out / Pipeline)"),
    ("prompt-optimization", "Prompt Optimization"),
    ("data-pipeline", "Data Pipeline / ETL"),
]
assert len(KEYS) == len(cats), f"{len(KEYS)} keys vs {len(cats)} categories"

loops = ROOT / "loops"
loops.mkdir(exist_ok=True)
(ROOT / "research").mkdir(exist_ok=True)


def prompt_md(i, p):
    stops = p.get("stop_conditions", [])
    stop = " · ".join(stops) if isinstance(stops, list) else str(stops)
    out = [f"### {i}. {p['title']}", ""]
    out.append(f"- **When:** {p.get('when_to_use','').strip()}")
    out.append(f"- **Loop:** {p.get('loop_shape','').strip()}")
    out.append(f"- **Stop:** {stop}")
    if p.get("model_notes"):
        out.append(f"- **Model:** {p['model_notes'].strip()}")
    out += ["", "```text", p["prompt_text"].strip(), "```", ""]
    return "\n".join(out)


# ---- category files ----
total = 0
for (key, title), cat in zip(KEYS, cats):
    prompts = cat.get("prompts", [])
    total += len(prompts)
    body = [f"# {title}", "", f"`{key}` — {len(prompts)} loop prompts.", ""]
    for i, p in enumerate(prompts, 1):
        body.append(prompt_md(i, p))
    (loops / f"{key}.md").write_text("\n".join(body))

# ---- loop-engineering principles (from best_practices) ----
bpmd = ["# Loop-engineering principles", "", bp.get("summary", "").strip(), "", "## Principles", ""]
for pr in bp.get("principles", []):
    bpmd.append(f"- **{pr['name']}** — {pr['detail']}")
bpmd += ["", "## Antipatterns (what makes a loop fail)", ""]
for a in bp.get("antipatterns", []):
    bpmd.append(f"- {a}")
(loops / "00-loop-engineering-principles.md").write_text("\n".join(bpmd) + "\n")

# ---- index ----
idx = ["# Loop-prompt library", "",
       f"**{total} reusable agent-loop prompts** across {len(KEYS)} loop families. "
       "Each is a copy-pasteable, model-agnostic prompt with an explicit stop condition so an agent "
       "iterates to a goal without looping forever.", "",
       "Start with [loop-engineering principles](00-loop-engineering-principles.md), then browse a family:", ""]
for (key, title), cat in zip(KEYS, cats):
    idx.append(f"- **[{title}]({key}.md)** — {len(cat.get('prompts', []))} prompts")
idx += ["", "## Starter set", "",
        "The most broadly useful prompts to try first (from curation):", ""]
for s in curation.get("starter_set", []):
    idx.append(f"- {s}")
if curation.get("notes"):
    idx += ["", "## Curation notes", "", curation["notes"].strip()]
if curation.get("duplicates"):
    idx += ["", "### Known near-duplicates (kept, but be aware)", ""]
    idx += [f"- {d}" for d in curation["duplicates"]]
(loops / "README.md").write_text("\n".join(idx) + "\n")

# ---- Fable-5 research report ----
rep = ["# How people actually use Claude Fable 5", "",
       "> Multi-agent web research, adversarially verified. Claims that could not be independently "
       "supported are flagged. Feeds the model-routing section of the prompt-loop-engineer agent.", ""]
for a in fable5:
    rep += [f"## Angle: {a['angle'].strip()}", "", a.get("summary", "").strip(), "", "**Findings:**", ""]
    for f in a.get("findings", []):
        src = f.get("source", "").strip()
        rep.append(f"- **[{f.get('confidence','?')}]** {f['claim']}")
        if f.get("detail"):
            rep.append(f"  - {f['detail'].strip()}")
        if src:
            rep.append(f"  - sources: {src}")
    rep.append("")
# verification table
rep += ["## Claim verification (adversarial)", "",
        "Top claims were handed to skeptic agents told to refute them:", "",
        "| Verdict | Claim | Note |", "|---|---|---|"]
for v in verdicts:
    claim = v["claim"].replace("|", "/")
    note = v["note"].replace("|", "/").replace("\n", " ")
    rep.append(f"| {v['supported']} | {claim[:120]} | {note[:160]} |")
(ROOT / "research" / "fable-5-usage.md").write_text("\n".join(rep) + "\n")

print(f"wrote {total} prompts across {len(KEYS)} category files")
print("wrote loops/README.md, loops/00-loop-engineering-principles.md, research/fable-5-usage.md")
# summary counts for routing enrichment
supp = sum(1 for v in verdicts if v["supported"] == "supported")
print(f"verdicts: {supp}/{len(verdicts)} supported")
