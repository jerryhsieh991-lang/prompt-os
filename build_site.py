#!/usr/bin/env python3
"""Build the prompt-os educational website from the loop-prompt library.

Source of truth: loops/*.md (14 family files, 8 prompts each) + loops/00-loop-engineering-principles.md.
Output: site/ — a static, dependency-free educational site:

    site/index.html              Home
    site/library.html            Searchable/filterable library of all 112 prompts (client-side)
    site/anatomy.html            The universal loop anatomy + principles
    site/prompt/<id>.html        112 prompt detail pages (Prompt / Anatomy / Why it works / Source)
    site/family/<key>.html       14 family pages (with curation/redundancy notes)
    site/data/prompts.json       Search index + full records
    site/assets/style.css        Design system
    site/assets/app.js           Search, filters, tabs, copy

Nothing here fabricates content: every field is parsed from the library, and the
"why it works" and "anatomy" views are derived deterministically from each prompt's
own text (paragraph labels + literal stop-arm anchors), grounded in the principles doc.

Run:  python3 build_site.py      # then open site/index.html
Stdlib only.
"""
from __future__ import annotations
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOPS = ROOT / "loops"
SITE = ROOT / "site"
ASSET_VER = "0"  # content hash of CSS+JS, set in build() for cache-busting

# Family order + human titles (keys match filenames).
FAMILIES = [
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
    ("image-generation", "Image Generation"),
    ("rag-answer", "RAG Answer"),
    ("browser-agent", "Browser Agent"),
    ("multi-agent", "Multi-Agent"),
    ("sql-analytics", "SQL / Analytics"),
    ("tool-use", "Tool Use"),
]

# One honest line per family (what the loop actually does).
FAMILY_DESC = {
    "build-verify": "Drive code to a passing bar — tests, contracts, benchmarks, budgets — one reversible change at a time.",
    "debug-rootcause": "Find the true cause behind a symptom: reproduce, bisect, probe, and prove the fix.",
    "redteam-verify": "Make a claim earn belief by surviving repeated adversarial attempts to refute it.",
    "refactor-safe": "Change structure without changing behavior, guarded by tests and small steps.",
    "research-until-dry": "Search, extract, and verify until new sources stop changing the answer.",
    "planning-decompose": "Turn a fuzzy request into an atomic, checkable leaf-task plan.",
    "test-generation": "Close coverage and edge-case gaps with tests that fail before the fix and pass after.",
    "review-dimensions": "Review a diff across fixed dimensions — bugs, security, performance, clarity — with verified findings.",
    "self-critique": "Draft → critique against a rubric → revise once, until the rubric is satisfied.",
    "migration-codemod": "Transform a frozen worklist of call-sites identically and safely.",
    "eval-benchmark": "Change one lever, re-run a frozen eval, keep only measured improvements.",
    "orchestration-harness": "Fan-out and pipeline patterns that wrap single-thread loops when parallelism pays.",
    "prompt-optimization": "The eval loop where the lever is restricted to the prompt text.",
    "data-pipeline": "Make an ETL step conform to a frozen schema and golden reference within tolerance.",
    "image-generation": "Iterate a generated image against a frozen brand/rubric checker until it passes — human gate before publish.",
    "rag-answer": "Answer from retrieved sources with every claim traced to a passage, or refuse.",
    "browser-agent": "Drive a browser by observe → act → verify the real page state → recover, human gate before payment.",
    "multi-agent": "Coordinate agents — supervisor/worker, debate, generator/critic, planner/executor — each checked by an independent frame.",
    "sql-analytics": "Text-to-SQL and analytics loops verified by running the query and asserting on the result, not by eyeballing.",
    "tool-use": "Call tools in a loop, verifying each call's real effect and recovering from errors instead of retrying blindly.",
}


def _discover_families():
    """Append any loops/<key>.md not already curated above — title taken from its H1.
    Lets a new family be added by just dropping a file; no code edit, so an automated
    round can't break the build by hand-editing FAMILIES."""
    known = {k for k, _ in FAMILIES}
    for path in sorted(LOOPS.glob("*.md")):
        key = path.stem
        if key in known or key == "README" or key.startswith("00"):
            continue
        head = path.read_text(encoding="utf-8")[:400]
        m = re.search(r"^#\s+(.+)$", head, re.M)
        FAMILIES.append((key, m.group(1).strip() if m else key.replace("-", " ").title()))
        known.add(key)


_discover_families()
FAMILY_TITLE = dict(FAMILIES)


def family_desc(key: str, title: str) -> str:
    return FAMILY_DESC.get(key, f"Agent-loop prompts for {title.lower()} — frozen goal, "
                                "independent verifier, multi-armed stop.")


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------

SECTION_RE = re.compile(r"^###\s+(\d+)\.\s+(.*)$", re.M)
FENCE_RE = re.compile(r"```(?:text)?\s*\n(.*?)\n```", re.S)
PLACEHOLDER_RE = re.compile(r"<[^>\n]{1,50}>")


def _field(block: str, name: str) -> str:
    m = re.search(rf"^-\s+\*\*{re.escape(name)}:\*\*\s*(.+)$", block, re.M)
    return m.group(1).strip() if m else ""


STOP_ARM_NAMES = ("SUCCESS", "BUDGET", "NO-PROGRESS", "BLOCKED")


def parse_stop_arms(stop: str) -> dict:
    """Anchor on the arm names and slice each description up to the next arm.

    Robust to separator style (':', '—', '-'), arm ordering, and descriptions
    that themselves contain '·' — which naive splitting broke on. Handles the
    Chinese self-critique family (arm names stay English, descriptions Chinese).
    """
    positions = []
    for arm in STOP_ARM_NAMES:
        m = re.search(rf"\b{re.escape(arm)}\b", stop)
        if m:
            positions.append((m.start(), m.end(), arm))
    positions.sort()
    arms = {}
    for i, (_s, e, arm) in enumerate(positions):
        nxt = positions[i + 1][0] if i + 1 < len(positions) else len(stop)
        desc = stop[e:nxt].strip(" :—–-·|\t").strip()
        arms[arm] = desc
    return arms


def split_title(title: str) -> tuple[str, str]:
    """For '中文(English)' titles, surface the English part; return (display, alt)."""
    m = re.match(r"^(.*?)[（(]\s*([^）)]*?)\s*[)）]\s*$", title.strip())
    if m and re.search(r"[A-Za-z]", m.group(2)) and re.search(r"[^\x00-\x7f]", m.group(1)):
        return m.group(2).strip(), m.group(1).strip()   # (English display, non-ASCII alt)
    return title, ""


def derive_verifier_type(model: str, prompt_text: str) -> str:
    """Honest facet: mechanical (execution ground-truth) vs judge (model/rubric)."""
    blob = (model + " " + prompt_text).lower()
    mechanical = any(k in blob for k in (
        "test suite", "benchmark", "schema valid", "compiler", "compile",
        "validator", "diff tool", "scanner", "coverage tool", "exit code",
        "serial", "plan", "back-translation", "field f1", "pass count", "golden",
    ))
    judge = any(k in blob for k in (
        "rubric", "judge", "persona", "fresh-reader", "fresh reader",
        "self-critique", "re-reads", "reviewer", "grade",
    ))
    if mechanical and not judge:
        return "mechanical"
    if judge and not mechanical:
        return "judge"
    if mechanical and judge:
        return "mixed"
    return "unspecified"


def derive_model_hint(model: str) -> str:
    m = model.lower()
    top = any(k in m for k in ("fable 5", "top-tier", "stronger model", "strongest"))
    cheap = any(k in m for k in ("cheaper", "haiku", "sonnet", "mid-tier", "high-volume", "mechanical"))
    if top and cheap:
        return "escalate"        # start cheap, escalate to top-tier
    if top:
        return "top-tier"
    if cheap:
        return "cheap"
    return "any"


def length_bucket(n: int) -> str:
    if n < 700:
        return "short"
    if n < 1100:
        return "medium"
    return "long"


def parse_family(key: str) -> list[dict]:
    path = LOOPS / f"{key}.md"
    text = path.read_text(encoding="utf-8")
    # fence-aware section headers: only '### N. Title' lines OUTSIDE ``` code fences,
    # so a prompt body that itself contains '### N.' can't split a section in two.
    headers = []  # (line_start, content_start, num, title)
    in_fence = False
    pos = 0
    for line in text.splitlines(keepends=True):
        s = line.rstrip("\n")
        if s.startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            m = re.match(r"^###\s+(\d+)\.\s+(.*)$", s)
            if m:
                headers.append((pos, pos + len(line), int(m.group(1)), m.group(2).strip()))
        pos += len(line)

    prompts = []
    for i, (_lstart, start, num, title) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        block = text[start:end]

        fence = FENCE_RE.search(block)
        prompt_text = fence.group(1).strip() if fence else ""
        when = _field(block, "When")
        loop = _field(block, "Loop")
        stop = _field(block, "Stop")
        model = _field(block, "Model")
        variables = sorted(set(PLACEHOLDER_RE.findall(prompt_text)))
        display_title, alt_title = split_title(title)

        prompts.append({
            "id": f"{key}-{num}",
            "num": num,
            "title": title,
            "display_title": display_title,
            "alt_title": alt_title,
            "family_key": key,
            "family_title": FAMILY_TITLE[key],
            "when": when,
            "loop": loop,
            "stop": stop,
            "stop_arms": parse_stop_arms(stop),
            "model": model,
            "prompt_text": prompt_text,
            "prompt_chars": len(prompt_text),
            "length_bucket": length_bucket(len(prompt_text)),
            "variables": variables,
            "verifier_type": derive_verifier_type(model, prompt_text),
            "model_hint": derive_model_hint(model),
            "starter": False,
        })
    return prompts


def parse_starter_titles() -> list[str]:
    text = (LOOPS / "README.md").read_text(encoding="utf-8")
    titles = []
    in_starter = False
    for line in text.splitlines():
        if line.startswith("## Starter set"):
            in_starter = True
            continue
        if in_starter and line.startswith("## "):
            break
        m = re.match(r"^-\s+\[[^\]]+\]\s+(.+)$", line.strip())
        if in_starter and m:
            titles.append(m.group(1).strip())
    return titles


def parse_principles() -> dict:
    text = (LOOPS / "00-loop-engineering-principles.md").read_text(encoding="utf-8")
    intro = ""
    m = re.search(r"^#\s+.*?\n\n(.+?)\n\n##", text, re.S)
    if m:
        intro = m.group(1).strip()
    principles = []
    for pm in re.finditer(r"^-\s+\*\*(.+?)\*\*\s*—\s*(.+)$", text, re.M):
        # Principles come before the Antipatterns section.
        principles.append({"name": pm.group(1).strip(), "body": pm.group(2).strip()})
    # Antipatterns are plain "- " bullets after "## Antipatterns"
    antipatterns = []
    ap = text.split("## Antipatterns", 1)
    if len(ap) == 2:
        for line in ap[1].splitlines():
            lm = re.match(r"^-\s+(.+)$", line.strip())
            if lm:
                antipatterns.append(lm.group(1).strip())
    # Keep only the 11 named principles (the ** ** bullets in the Principles section)
    principles = [p for p in principles if "—" not in p["name"]][:11]
    return {"intro": intro, "principles": principles, "antipatterns": antipatterns}


def parse_curation_note(key: str) -> str:
    """Pull any near-duplicate lines from README that mention this family."""
    text = (LOOPS / "README.md").read_text(encoding="utf-8")
    hits = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- ") and key in s and "≈" in s:
            hits.append(s[2:])
    return "\n".join(hits)


# ----------------------------------------------------------------------------
# Anatomy: classify each prompt paragraph + inline-highlight literal anchors
# ----------------------------------------------------------------------------

ANAT_LABELS = {
    "goal": "Frozen goal",
    "verifier": "Independent verifier",
    "action": "One action / turn",
    "state": "Compact state",
    "stop": "Stop condition",
    "context": "Context",
}
ANAT_ORDER = ["goal", "verifier", "action", "state", "stop", "context"]

# Ordered anchor label -> loop role. These inline markers appear in BOTH the
# blank-line-separated prompts and the dense single-paragraph ones (redteam,
# test-gen, review, prompt-opt families), so anchor-splitting handles all 112
# uniformly where paragraph-splitting collapsed a whole prompt into one block.
_ANCHORS: list[tuple[str, str]] = [
    ("goal", r"GOAL \(frozen\)|Goal \(frozen\)|Frozen goal|GOAL:|Goal:|"
             r"Freeze the goal[^:.\n]*|Freeze the claim[^:.\n]*|Freeze the finding[^:.\n]*|"
             r"Freeze the conclusion[^:.\n]*|Freeze the thesis[^:.\n]*|Freeze the stated[^:.\n]*|"
             r"Freeze the root[^:.\n]*|Freeze this[^:.\n]*|Before turn 1, freeze[^:.\n]*|Target:"),
    ("verifier", r"VERIFIER:|Verifier:"),
    ("action", r"LOOP \(each turn\)|Each turn|Each round|Per turn|Turn shape|Every turn|"
               r"First turn|Baseline first|Start by"),
    ("state", r"Carry forward|Carry state|Carry compact|Maintain a |Maintain this |State log"),
    # A Stop/Halt clause is the word 'Stop'/'Halt' immediately followed (within one
    # sentence) by the uppercase arm enumeration. High precision: won't match a stray
    # 'don't stop early', catches every lead-in ('STOP on first', 'Halt the moment
    # any exit trips', 'Stop immediately on', 'Stop the instant one arm trips').
    ("stop", r"(?:STOP|Stop|HALT|Halt)\b(?=[^.]{0,90}?\b(?:SUCCESS|BUDGET|NO-PROGRESS|BLOCKED)\b)"),
]


def segment_anatomy(text: str) -> list[tuple[str, str]]:
    """Split a prompt into (role, text) segments at inline anchor labels.

    Works whether the prompt uses blank lines or is one dense paragraph. Text
    before the first anchor is the goal (these prompts always open by stating it).
    Consecutive same-role segments are merged.
    """
    text = text.strip()
    hits: list[tuple[int, str]] = []
    for role, pat in _ANCHORS:
        for m in re.finditer(pat, text):
            hits.append((m.start(), role))
    hits.sort()
    # drop anchors that collide within a couple chars (keep the earliest/highest-priority)
    cleaned: list[tuple[int, str]] = []
    for pos, role in hits:
        if cleaned and pos - cleaned[-1][0] < 3:
            continue
        cleaned.append((pos, role))
    if not cleaned:
        return [("goal", text)]

    segs: list[tuple[str, str]] = []
    if cleaned[0][0] > 0:
        lead = text[:cleaned[0][0]].strip()
        if lead:
            segs.append(("goal", lead))
    for i, (pos, role) in enumerate(cleaned):
        end = cleaned[i + 1][0] if i + 1 < len(cleaned) else len(text)
        seg = text[pos:end].strip()
        if seg:
            segs.append((role, seg))
    merged: list[tuple[str, str]] = []
    for role, seg in segs:
        if merged and merged[-1][0] == role:
            merged[-1] = (role, merged[-1][1] + " " + seg)
        else:
            merged.append((role, seg))
    return merged


# Stop arms are UPPERCASE and matched case-sensitively; their lowercase class names
# ('arm-success') can't be re-matched — so a per-arm loop is safe here.
_STOP_HL = re.compile(r"\b(SUCCESS|BUDGET|NO-PROGRESS|BLOCKED)\b")
_STOP_CLASS = {"SUCCESS": "arm-success", "BUDGET": "arm-budget",
               "NO-PROGRESS": "arm-noprogress", "BLOCKED": "arm-blocked"}
# Verify/invariant terms are case-INSENSITIVE, so they MUST be highlighted in a
# single pass — a second pass would match 'verify' inside an already-inserted
# class="hl-verify" attribute and shatter the tag. Longest alternatives first.
_KW_HL = re.compile(
    r"\b(?P<v>independent verifier|as the verifier|as your verifier|as verifier|"
    r"independent check|verifier|verify)\b"
    r"|\b(?P<i>git reset|commit|revert)\b", re.I)


def highlight_inline(escaped: str, anat: str) -> str:
    """Wrap literal anchor keywords (input already HTML-escaped, so it has no real tags)."""
    if anat == "stop":
        return _STOP_HL.sub(lambda m: f'<span class="{_STOP_CLASS[m.group(1)]}">{m.group(1)}</span>', escaped)
    if anat in ("action", "context", "verifier"):
        return _KW_HL.sub(
            lambda m: (f'<span class="hl-verify">{m.group(0)}</span>' if m.group("v")
                       else f'<span class="hl-invariant">{m.group(0)}</span>'), escaped)
    return escaped


def render_anatomy(prompt_text: str, reveal: bool = False) -> str:
    blocks = []
    rc = " reveal" if reveal else ""
    for anat, seg in segment_anatomy(prompt_text):
        esc = html.escape(seg)
        esc = highlight_inline(esc, anat)
        esc = esc.replace("\n", "<br>")
        blocks.append(
            f'<div class="anat anat-{anat}{rc}">'
            f'<span class="anat-label">{ANAT_LABELS[anat]}</span>'
            f'<div class="anat-body">{esc}</div></div>'
        )
    return "\n".join(blocks)


# "Why it works" is derived per-prompt from the prompt's OWN text: a principle is
# shown only when it's actually detectable, with a quote from this prompt as evidence.

def _short(s: str, n: int = 170) -> str:
    """Collapse whitespace, strip a leading anatomy label, cap length, HTML-escape."""
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(GOAL \(frozen\)|Goal \(frozen\)|GOAL|Goal|VERIFIER|Verifier|"
               r"Carry forward[^:]*|LOOP \([^)]*\)|Turn shape)\s*[:.]?\s*", "", s)
    if len(s) > n:
        s = s[:n].rsplit(" ", 1)[0] + "…"
    return html.escape(s)


def _find(text: str, pat: str) -> str | None:
    m = re.search(pat, text, re.I)
    return m.group(1) if m else None


def why_points(p: dict) -> list[tuple[str, str | None, str]]:
    """Return (principle, anatomy-role-or-None, evidence-html) grounded in THIS prompt."""
    text = p["prompt_text"]
    low = text.lower()
    segs = segment_anatomy(text)
    roles = {r for r, _ in segs}
    pts: list[tuple[str, str | None, str]] = []

    # Frozen goal — always present; quote it.
    goal_seg = next((seg for r, seg in segs if r == "goal"), text)
    pts.append(("Anchor to a measurable, frozen goal", "goal",
                f"“{_short(goal_seg, 190)}”"))

    # Independent verifier — always; characterize + quote the actual verifier clause.
    vt = p["verifier_type"]
    vclause = _find(text, r"(verified by [^.;]+|as (?:your|the) verifier[^.;]*|"
                          r"VERIFIER:[^.;]+|independent check[^.;]*|"
                          r"independent(?:ly)? (?:verified|corroborat)[^.;]*)")
    vtxt = (f"Verifier here is <strong>{vt}</strong>. " if vt in ("mechanical", "judge", "mixed") else "")
    vtxt += (f"“{_short(vclause, 150)}”" if vclause
             else "the mechanism that decides “done” is separate from what’s being changed.")
    pts.append(("Verify with an independent signal, not self-assessment", "verifier", vtxt))

    # One reversible action per turn.
    if "action" in roles or re.search(r"\bONE\b", text):
        a = _find(text, r"(make (?:the )?(?:smallest|one)[^.;]+|exactly ONE[^.;]+|"
                        r"ONE (?:reversible |source |transform |resource |optimization |handler[- ]behavior )?[^.;]+)")
        if a:
            pts.append(("One reversible action per turn, then observe", "action", f"“{_short(a, 150)}”"))

    # Known-good invariant.
    if "commit" in low and ("git reset" in low or "revert" in low or "discard" in low):
        pts.append(("Preserve a known-good workspace each turn", None,
                    "Commit on improvement, revert on regression — a bad turn can’t corrupt the baseline."))

    # Compact state.
    if "state" in roles:
        s = next((seg for r, seg in segs if r == "state"), "")
        pts.append(("Carry compact state across turns", "state", f"“{_short(s, 160)}”"))

    # Break non-progress / oscillation.
    if re.search(r"never repeat|different approach|materially different|don't keep grinding|"
                 r"oscillat|never the identical|never retry the identical|not a re-?tuned", low):
        n = _find(text, r"([^.;]*?(?:never repeat|different approach|materially different|"
                        r"don't keep grinding|oscillat|never the identical|never retry the identical|"
                        r"not a re-?tuned)[^.;]*)")
        pts.append(("Detect and break non-progress and oscillation", None,
                    f"“{_short(n, 150)}”" if n else "A retry must change approach, not re-attempt the same thing."))

    # Freeze scope / ban gold-plating. (Deliberately excludes goal-describing phrases
    # like 'zero behavior change' so the evidence is an actual scope-ban instruction,
    # not a re-quote of the goal.)
    if re.search(r"do not edit|don't edit|off-limits|while i'm here|do not adopt|not the moment|"
                 r"scope is|don't loosen|park those|don't redesign|don't hand-tune|don't refactor", low):
        f = _find(text, r"([^.;]*?(?:do not edit|don't edit|off-limits|while I'm here|do not adopt|"
                        r"not the moment|scope is|don't loosen|park those|don't redesign|don't hand-tune|"
                        r"don't refactor)[^.;]*)")
        pts.append(("Freeze scope and ban gold-plating", None,
                    f"“{_short(f, 150)}”" if f else "The loop closes the defined gap and nothing else."))

    # Research saturation.
    if p["family_key"] == "research-until-dry" or "dry counter" in low or "stale counter" in low or "saturat" in low:
        pts.append(("For research loops, define saturation (‘dry’)", None,
                    "It stops when new sources stop changing the answer — evidence-saturated, not effort-exhausted."))

    # Escalate, don't grind.
    if re.search(r"escalate|hand off|hand it off|request human|needs a human|human can make|"
                 r"only a human|wait for a human", low):
        pts.append(("Fail loud after repeated failure; escalate, don’t grind", None,
                    "When progress stalls or a call needs a human, it halts and surfaces what was tried."))

    return pts


# ----------------------------------------------------------------------------
# Analysis engine — DETERMINISTIC (no LLM). Patterns, complexity, stats, relations.
# Using a model to "count" these would misuse AI for a deterministic step — the
# exact automation antipattern this corpus teaches. So it's plain code.
# ----------------------------------------------------------------------------

# Discriminating patterns (universal ones like the frozen goal / BUDGET arm are
# omitted — a pattern is only interesting when it separates prompts). `blurb` is a
# seed one-liner; the richer reference prose is authored by the pattern workflow.
PATTERN_META = [
    ("commit-revert", "Known-good invariant", "goal",
     "Commit on improvement, revert on regression, so a bad turn can't corrupt the baseline."),
    ("anti-oscillation", "Anti-oscillation", None,
     "Ban verbatim retries; a new attempt must change approach, not repeat a failed one."),
    ("human-escalation", "Human escalation", "stop",
     "When a call needs a human or a resource is missing, stop and hand off with context."),
    ("freeze-scope", "Freeze scope", None,
     "Close the defined gap and nothing else; park 'while I'm here' ideas."),
    ("mechanical-verifier", "Mechanical verifier", "verifier",
     "Decide 'done' by execution ground-truth — tests, benchmark, schema, compiler, scanner."),
    ("judge-rubric", "Judge / rubric", "verifier",
     "Score against a rubric or judge where there's no ground truth; define it before the loop."),
    ("adversarial-verify", "Adversarial verification", "verifier",
     "A claim counts only if it survives an independent attempt to refute it."),
    ("regression-first", "Regression-test-first", "verifier",
     "Codify the bug as a failing test and freeze it before touching the source."),
    ("research-saturation", "Research saturation", None,
     "Stop when new sources stop changing the answer — evidence-saturated, not effort-exhausted."),
    ("fan-out", "Fan-out", "action",
     "Run N subagents in parallel over independent items, then merge."),
    ("pipeline", "Pipeline", "action",
     "Route each item through fixed stages, each stage its own verified step."),
    ("ratchet", "Ratchet", None,
     "A per-file/metric counter that may only move toward the target, never backward."),
    ("characterization-test", "Characterization test", "verifier",
     "Pin down existing behavior with tests before refactoring, so change preserves it."),
    ("worklist-codemod", "Worklist codemod", "action",
     "Transform a frozen list of call-sites identically without re-scoping mid-run."),
    ("shadow-verify", "Shadow / expand-migrate-contract", "verifier",
     "Run the new path beside the old and compare before cutting over."),
]
PATTERN_NAME = {k: n for k, n, _, _ in PATTERN_META}


# ---- Automation archetypes --------------------------------------------------
# Illustrative reference workflows (NOT scraped from a platform, NOT measured).
# The value is the STRUCTURE: each step is typed AI vs deterministic vs human vs
# validation/fallback, which is the one thing most "AI automation" content gets
# wrong. The step sequence is authored here; the prose (goal / why-AI / failure
# modes / reliability) is agent-authored and adversarially verified.
STEP_LABELS = {
    "trigger":       ("Trigger", "step-trigger"),
    "deterministic": ("Deterministic", "step-det"),
    "ai":            ("AI decision", "step-ai"),
    "validation":    ("Validation", "step-val"),
    "decision":      ("Decision gate", "step-dec"),
    "human":         ("Human approval", "step-human"),
    "fallback":      ("Fallback", "step-fallback"),
    "notification":  ("Notification", "step-notify"),
    "store":         ("Data store", "step-store"),
}

AUTOMATIONS = [
    {"key": "inbox-triage", "name": "Inbox triage & reply draft", "category": "Email",
     "schedule": "on new inbound email", "retry": "retry send 3× with backoff; never re-send on ambiguous success",
     "steps": [
         ("trigger", "New email lands in a watched inbox"),
         ("ai", "Classify intent, urgency, and required action"),
         ("deterministic", "Route to a queue by rules (VIP, billing, spam)"),
         ("ai", "Draft a reply grounded in the thread + knowledge base"),
         ("validation", "Check tone, policy, and that no promise/PII leaks"),
         ("human", "Person approves, edits, or rejects the draft"),
         ("deterministic", "Send, label, and archive"),
         ("store", "Log intent, action taken, and latency"),
     ]},
    {"key": "research-digest", "name": "Scheduled research digest", "category": "Research",
     "schedule": "daily at 07:00", "retry": "per-source retry; skip a dead source, don't fail the whole run",
     "steps": [
         ("trigger", "Cron fires on schedule"),
         ("deterministic", "Fetch the configured sources / feeds"),
         ("ai", "Summarize and cluster what's genuinely new"),
         ("validation", "Drop items with no source URL; cap length"),
         ("human", "Optional: approve before send for sensitive lists"),
         ("deterministic", "Render and email the digest"),
         ("store", "Snapshot sources so tomorrow can diff against today"),
     ]},
    {"key": "doc-extract", "name": "Document → extract → validate → store", "category": "Documents",
     "schedule": "on new file in a folder / bucket", "retry": "reprocess on transient OCR failure; quarantine on repeat",
     "steps": [
         ("trigger", "New document arrives (upload, email, scan)"),
         ("deterministic", "Parse / OCR to text + layout"),
         ("ai", "Extract the target fields into a schema"),
         ("validation", "Validate types, required fields, and ranges"),
         ("decision", "Confidence ≥ threshold?"),
         ("store", "Write clean records to the database"),
         ("fallback", "Below threshold → route to a human review queue"),
     ]},
    {"key": "support-triage", "name": "Support ticket triage & draft", "category": "Customer support",
     "schedule": "on new ticket", "retry": "idempotent by ticket id; never double-post a reply",
     "steps": [
         ("trigger", "New support ticket created"),
         ("ai", "Classify topic, sentiment, and severity"),
         ("deterministic", "Assign / prioritize by routing rules + SLA"),
         ("ai", "Draft a reply from the knowledge base"),
         ("validation", "Policy + hallucinated-fact check against KB"),
         ("human", "Agent approves or edits before it goes out"),
         ("deterministic", "Post reply, set status, start SLA timer"),
     ]},
    {"key": "pr-review", "name": "PR review assistant", "category": "Coding",
     "schedule": "on pull request opened / updated", "retry": "re-run on new commits; comment is idempotent per SHA",
     "steps": [
         ("trigger", "Pull request opened or pushed"),
         ("deterministic", "Run tests, linters, and security scanners"),
         ("ai", "Review the diff for bugs, clarity, and risk"),
         ("validation", "Keep only findings tied to a changed line"),
         ("deterministic", "Post findings as one PR comment"),
         ("decision", "Blocking issue found?"),
         ("human", "A human still owns the merge decision"),
     ]},
    {"key": "content-repurpose", "name": "Content repurpose pipeline", "category": "Content",
     "schedule": "on new published piece", "retry": "regenerate a failed variant only; keep the good ones",
     "steps": [
         ("trigger", "A new article / video is published"),
         ("ai", "Generate channel-specific variants (social, email, thread)"),
         ("validation", "Brand-voice + claims + length checks per channel"),
         ("human", "Approve the batch (or per-channel)"),
         ("deterministic", "Schedule / publish to each channel"),
         ("store", "Record which variant shipped where"),
     ]},
    {"key": "anomaly-alert", "name": "Metric anomaly → diagnose → alert", "category": "Monitoring",
     "schedule": "on metric threshold breach", "retry": "dedupe + rate-limit alerts; escalate only if unresolved",
     "steps": [
         ("trigger", "A metric crosses a threshold"),
         ("deterministic", "Confirm it's sustained, not a single spike"),
         ("ai", "Diagnose the likely cause from recent changes + logs"),
         ("deterministic", "Dedupe against open incidents; rate-limit"),
         ("notification", "Alert the on-call with the diagnosis attached"),
         ("decision", "Still breaching after N minutes?"),
         ("fallback", "Escalate to the next tier"),
     ]},
    {"key": "lead-enrich", "name": "Lead enrich → score → CRM", "category": "Sales / CRM",
     "schedule": "on new lead", "retry": "cache enrichment; re-score without re-enriching",
     "steps": [
         ("trigger", "New lead submitted"),
         ("deterministic", "Enrich from configured data sources"),
         ("ai", "Qualify and score fit against the ICP"),
         ("decision", "Score ≥ routing threshold?"),
         ("store", "Write lead + score + reasoning to the CRM"),
         ("fallback", "Low-confidence → flag for SDR review, don't auto-route"),
     ]},
    {"key": "batch-conformance", "name": "Batch conformance & quarantine", "category": "Data",
     "schedule": "on new batch / nightly", "retry": "reprocess quarantined rows after a fix; idempotent load",
     "steps": [
         ("trigger", "A new data batch arrives"),
         ("validation", "Validate every row against the frozen schema"),
         ("ai", "Repair / classify malformed rows where safe"),
         ("validation", "Re-validate the repaired rows"),
         ("store", "Load clean rows to the warehouse"),
         ("fallback", "Unfixable rows → quarantine table + report"),
     ]},
    {"key": "meeting-actions", "name": "Meeting notes → action items", "category": "Productivity",
     "schedule": "on transcript ready", "retry": "idempotent per meeting id; don't duplicate tasks",
     "steps": [
         ("trigger", "Meeting transcript becomes available"),
         ("ai", "Extract decisions, owners, and action items"),
         ("validation", "Require an owner + due date per action"),
         ("human", "Attendee confirms the extracted list"),
         ("deterministic", "Create tasks in the tracker"),
         ("store", "Link tasks back to the meeting"),
     ]},
    {"key": "social-respond", "name": "Social mention → classify → respond", "category": "Social media",
     "schedule": "on new mention", "retry": "idempotent per mention id; human-gated before any public post",
     "steps": [
         ("trigger", "Brand is mentioned"),
         ("ai", "Classify sentiment, intent, and risk"),
         ("deterministic", "Route: ignore / thank / support / escalate"),
         ("ai", "Draft an on-brand response"),
         ("human", "Approve before anything is posted publicly"),
         ("deterministic", "Post and record the thread"),
     ]},
    {"key": "competitor-watch", "name": "Scheduled competitor watch", "category": "Research",
     "schedule": "weekly", "retry": "per-page retry; a fetch failure skips that page only",
     "steps": [
         ("trigger", "Cron fires weekly"),
         ("deterministic", "Fetch the watched pages"),
         ("deterministic", "Diff against last week's snapshot"),
         ("ai", "Summarize what materially changed and why it matters"),
         ("decision", "Anything material?"),
         ("notification", "Notify the team; else stay silent"),
     ]},
]
AUTOMATION_CATEGORIES = []
for _a in AUTOMATIONS:
    if _a["category"] not in AUTOMATION_CATEGORIES:
        AUTOMATION_CATEGORIES.append(_a["category"])


def detect_patterns(p: dict) -> set:
    """Which discriminating patterns THIS prompt exhibits (keyword/field evidence)."""
    text, low, fk = p["prompt_text"], p["prompt_text"].lower(), p["family_key"]
    found = set()

    def has(*subs):
        return any(s in low for s in subs)

    if "commit" in low and ("git reset" in low or "revert" in low or "discard" in low):
        found.add("commit-revert")
    if has("never repeat", "different approach", "materially different",
           "never the identical", "not a re-tuned", "not a retuned", "oscillat"):
        found.add("anti-oscillation")
    if has("escalate", "hand off", "hand it off", "request human", "needs a human",
           "human can make", "only a human", "wait for a human"):
        found.add("human-escalation")
    if has("do not edit", "don't edit", "off-limits", "while i'm here", "do not adopt",
           "don't refactor", "scope is", "park those", "don't loosen", "don't hand-tune", "not the moment"):
        found.add("freeze-scope")
    if p["verifier_type"] == "mechanical":
        found.add("mechanical-verifier")
    if p["verifier_type"] == "judge":
        found.add("judge-rubric")
    if fk == "redteam-verify" or has("adversarial", "refute", "skeptic", "red team", "red-team"):
        found.add("adversarial-verify")
    if "regression" in low and has("regression test", "failing test", "reproduce", "frozen"):
        found.add("regression-first")
    if fk == "research-until-dry" or has("dry counter", "stale counter", "saturat", "no new"):
        found.add("research-saturation")
    if has("fan-out", "fan out", "subagent", "sub-agent", "in parallel", "parallelize"):
        found.add("fan-out")
    if "pipeline" in low or "stage" in low and has("stage 1", "each stage", "stages"):
        if "pipeline" in low or "stages" in low:
            found.add("pipeline")
    if has("ratchet", "strictness", "per-file error", "error count", "error-count"):
        found.add("ratchet")
    if "characterization" in low:
        found.add("characterization-test")
    if fk == "migration-codemod" or has("worklist", "codemod", "call-site", "call site"):
        found.add("worklist-codemod")
    if has("shadow", "expand-migrate-contract", "expand, migrate", "dual-write", "dual write", "shadow-read"):
        found.add("shadow-verify")
    return found


def complexity_profile(p: dict) -> dict:
    """Countable structural facts — no fabricated 0-100 score, just the real counts + a band."""
    text = p["prompt_text"]
    steps = len(re.findall(r"\(\d+\)", text)) or len([s for s in re.split(r"\s*->\s*|\s*→\s*", p["loop"]) if s.strip()])
    decisions = len(re.findall(r"\bif\b", text, re.I))
    nested = len(re.findall(r"\([a-e]\)", text))
    prof = {
        "steps": steps,
        "stop_arms": len(p["stop_arms"]),
        "variables": len(p["variables"]),
        "decisions": decisions,
        "patterns": len(detect_patterns(p)),
        "nested": nested,
        "chars": p["prompt_chars"],
    }
    score = prof["steps"] + prof["patterns"] + prof["decisions"] + prof["nested"] + prof["variables"] // 2
    prof["band"] = "compact" if score < 10 else "standard" if score < 16 else "dense"
    return prof


def parse_redundancy_map(prompts: list[dict]) -> dict:
    """Explicit cross-family relatives from the library's own '≈' curation lines (README).

    These hand-authored near-duplicate notes are the gold 'these are relatives' signal —
    they connect the SAME loop across different families, which pattern-overlap alone misses.
    """
    text = (LOOPS / "README.md").read_text(encoding="utf-8")
    # title -> prompt id (match a quoted curation title to a real prompt title)
    title_to_id = {}
    for p in prompts:
        title_to_id[p["title"].lower()] = p["id"]
        title_to_id[p["display_title"].lower()] = p["id"]
    edges: dict[str, set] = {p["id"]: set() for p in prompts}
    for line in text.splitlines():
        if "≈" not in line:
            continue
        quoted = re.findall(r"'([^']+)'", line)
        ids = []
        for q in quoted:
            ql = q.lower()
            hit = title_to_id.get(ql) or next((i for t, i in title_to_id.items() if ql in t or t in ql), None)
            if hit:
                ids.append(hit)
        for a in ids:
            for c in ids:
                if a != c:
                    edges[a].add(c)
    return edges


def build_related(prompts: list[dict]) -> dict:
    """Relatives: explicit curation '≈' edges first, then highest pattern-overlap (any family)."""
    by_id = {p["id"]: p for p in prompts}
    pat = {p["id"]: detect_patterns(p) for p in prompts}
    curation = parse_redundancy_map(prompts)
    related = {}
    for p in prompts:
        picked, seen = [], {p["id"]}
        # tier 1 — explicit near-duplicates from curation notes
        for qid in curation[p["id"]]:
            if qid not in seen:
                picked.append((by_id[qid], len(pat[p["id"]] & pat[qid]), True))
                seen.add(qid)
        # tier 2 — fill remaining slots by pattern overlap (no same-family bias)
        scores = []
        for q in prompts:
            if q["id"] in seen:
                continue
            shared = pat[p["id"]] & pat[q["id"]]
            if not shared:
                continue
            j = len(shared) / max(1, len(pat[p["id"]] | pat[q["id"]]))
            scores.append((j, len(shared), q["id"]))
        scores.sort(reverse=True)
        for _j, sh, qid in scores:
            if len(picked) >= 5:
                break
            picked.append((by_id[qid], sh, False))
            seen.add(qid)
        related[p["id"]] = picked[:5]
    return related


def corpus_stats(prompts: list[dict]) -> dict:
    import collections
    pat_counts = collections.Counter()
    vt = collections.Counter()
    mh = collections.Counter()
    principle_sets = set()
    for p in prompts:
        for k in detect_patterns(p):
            pat_counts[k] += 1
        vt[p["verifier_type"]] += 1
        mh[p["model_hint"]] += 1
        principle_sets.add(tuple(sorted(pr for pr, _, _ in why_points(p))))
    return {
        "total": len(prompts),
        "families": len(FAMILIES),
        "patterns_tracked": len(PATTERN_META),
        "principle_sets": len(principle_sets),
        "starter": sum(1 for p in prompts if p["starter"]),
        "verifier_breakdown": dict(vt),
        "model_breakdown": dict(mh),
        "pattern_counts": dict(pat_counts),
        "mechanical": vt.get("mechanical", 0),
        "avg_patterns": round(sum(len(detect_patterns(p)) for p in prompts) / len(prompts), 1),
        # honest, corpus-computed metrics (verified prompts kept SEPARATE from automation workflows)
        "research_loop": pat_counts.get("research-saturation", 0),
        "anti_oscillation": pat_counts.get("anti-oscillation", 0),
        "validation_types": len([k for k in vt if k in ("mechanical", "judge", "mixed")]),
        "automation_workflows": len(AUTOMATIONS),
    }


# ----------------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------------

def page(title: str, body: str, prefix: str, *, desc: str = "", extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>document.documentElement.classList.add('js');try{{if(!matchMedia('(prefers-reduced-motion: reduce)').matches)document.documentElement.classList.add('motion-ok');}}catch(e){{}}</script>
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%233a4ce0'/%3E%3Cpath d='M11 16a5 5 0 1 1 5 5' fill='none' stroke='white' stroke-width='3' stroke-linecap='round'/%3E%3Cpath d='M16 17l-5 4v-8z' fill='white'/%3E%3C/svg%3E">
<link rel="stylesheet" href="{prefix}assets/style.css?v={ASSET_VER}">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap head-inner">
    <a class="brand" href="{prefix}index.html">prompt<span>·</span>os</a>
    <nav>
      <a href="{prefix}library.html">Library</a>
      <a href="{prefix}patterns.html">Patterns</a>
      <a href="{prefix}graph.html">Graph</a>
      <a href="{prefix}loops.html">Loops</a>
      <a href="{prefix}automation.html">Automation</a>
      <a href="{prefix}families.html">Families</a>
      <a href="{prefix}anatomy.html">Anatomy</a>
      <a href="{prefix}glossary.html">Glossary</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <p>112 agent-loop prompts · 14 families · one shared anatomy.
    Content from the <strong>prompt-os</strong> loop library — generated by a
    32-agent research→verify→curate pipeline, human-reviewed. Every prompt has an
    explicit stop condition; nothing loops forever.</p>
    <p class="muted">Static site generated from <code>loops/*.md</code> by <code>build_site.py</code>.
    No tracking, no external requests.</p>
  </div>
</footer>
<script src="{prefix}assets/app.js?v={ASSET_VER}" defer></script>
</body>
</html>
"""


def chip(text: str, cls: str = "") -> str:
    return f'<span class="chip {cls}">{html.escape(text)}</span>'


def facet_chips(p: dict) -> str:
    out = [chip(p["family_title"], "chip-family")]
    if p["starter"]:
        out.append(chip("starter", "chip-starter"))
    vt = p["verifier_type"]
    if vt in ("mechanical", "judge", "mixed"):
        out.append(chip(f"{vt} verifier", f"chip-verifier chip-{vt}"))
    out.append(chip(f"{p['model_hint']} model", "chip-model"))
    return "".join(out)


def card_title_html(p: dict, num: bool = False) -> str:
    """Card title: English display line, with the non-ASCII original muted beneath."""
    label = f'{p["num"]}. {p["display_title"]}' if num else p["display_title"]
    out = f'<span class="pcard-title">{html.escape(label)}</span>'
    if p["alt_title"]:
        out += f'<span class="pcard-alt">{html.escape(p["alt_title"])}</span>'
    return out


def loop_steps_html(loop: str) -> str:
    steps = [s.strip() for s in re.split(r"\s*->\s*|\s*→\s*", loop) if s.strip()]
    return '<ol class="loop-steps">' + "".join(f"<li>{html.escape(s)}</li>" for s in steps) + "</ol>"


def stop_arms_html(arms: dict) -> str:
    order = [("SUCCESS", "arm-success"), ("BUDGET", "arm-budget"),
             ("NO-PROGRESS", "arm-noprogress"), ("BLOCKED", "arm-blocked")]
    rows = []
    for name, cls in order:
        if name in arms:
            rows.append(f'<div class="stoparm {cls}"><span class="arm-name">{name}</span>'
                        f'<span class="arm-body">{html.escape(arms[name])}</span></div>')
    return '<div class="stoparms">' + "".join(rows) + "</div>"


# ---- Detail page ------------------------------------------------------------

def render_detail(p: dict, related_list: list) -> str:
    prefix = "../"
    esc_prompt = html.escape(p["prompt_text"])

    pats = [k for k, _n, _r, _b in PATTERN_META if k in detect_patterns(p)]
    pattern_chips = "".join(
        f'<a class="chip chip-pattern" href="{prefix}pattern/{k}.html">{html.escape(PATTERN_NAME[k])}</a>'
        for k in pats
    )
    cx = complexity_profile(p)
    cx_items = [("steps", cx["steps"]), ("stop arms", cx["stop_arms"]),
                ("patterns", cx["patterns"]), ("variables", cx["variables"]),
                ("decisions", cx["decisions"])]
    complexity_html = (
        f'<div class="cx"><span class="cx-band cx-{cx["band"]}">{cx["band"]} structure</span>'
        + "".join(f'<span class="cx-item"><b>{v}</b> {html.escape(lbl)}</span>' for lbl, v in cx_items)
        + "</div>"
    )
    related_html = ""
    if related_list:
        cards = "".join(
            f'<a class="rel-card" href="{prefix}prompt/{q["id"]}.html">'
            f'<span class="rel-fam">{html.escape(q["family_title"])}</span>'
            f'<span class="rel-title">{html.escape(q["display_title"])}</span>'
            f'<span class="rel-why">{"★ same loop, different framing" if cur else (str(sh) + " shared pattern" + ("s" if sh != 1 else ""))}</span>'
            f'</a>'
            for q, sh, cur in related_list
        )
        related_html = (f'<section class="related"><h2 class="section-h">Related prompts</h2>'
                        f'<p class="section-sub">Nearest relatives — from the library’s own near-duplicate '
                        f'notes (★) and shared patterns.</p><div class="rel-grid">{cards}</div></section>')
    vars_html = ""
    if p["variables"]:
        vars_html = ('<div class="vars"><span class="vars-label">Fill in:</span> '
                     + " ".join(f'<code class="var">{html.escape(v)}</code>' for v in p["variables"])
                     + "</div>")

    why_items = []
    for principle, role, evidence in why_points(p):
        dot = (f'<span class="why-dot anat-dot-{role}"></span>' if role
               else '<span class="why-dot why-dot-plain"></span>')
        why_items.append(
            f'<li>{dot}<div class="why-text"><strong>{html.escape(principle)}.</strong> '
            f'<span class="why-ev">{evidence}</span></div></li>'
        )
    why_html = "<ul class='why-list'>" + "".join(why_items) + "</ul>"

    dup_note = parse_curation_note(p["family_key"])
    dup_html = ""
    if dup_note:
        dup_html = ("<p class='dup'><strong>Known near-duplicates in the library</strong> "
                    "(kept deliberately, as an educational signal that the same loop recurs "
                    "under different framings):</p><ul class='dup-list'>"
                    + "".join(f"<li>{html.escape(l)}</li>" for l in dup_note.splitlines())
                    + "</ul>")

    body = f"""
<div class="wrap detail">
  <p class="crumbs"><a href="{prefix}library.html">Library</a> ›
     <a href="{prefix}family/{p['family_key']}.html">{html.escape(p['family_title'])}</a> ›
     <span>{html.escape(p['display_title'])}</span></p>

  <h1 class="detail-title">{html.escape(p['display_title'])}</h1>
  {f'<p class="detail-alt">{html.escape(p["alt_title"])}</p>' if p['alt_title'] else ''}
  <p class="detail-when">{html.escape(p['when'])}</p>
  <div class="facets">{facet_chips(p)}</div>
  {f'<div class="patternrow"><span class="patternrow-label">Patterns</span>{pattern_chips}</div>' if pattern_chips else ''}

  <div class="tabs" role="tablist">
    <button class="tab is-active" data-tab="prompt" role="tab">Prompt</button>
    <button class="tab" data-tab="anatomy" role="tab">Anatomy</button>
    <button class="tab" data-tab="why" role="tab">Why it works</button>
    <button class="tab" data-tab="source" role="tab">Source</button>
  </div>

  <section class="tabpanel is-active" data-panel="prompt">
    {vars_html}
    <div class="prompt-toolbar">
      <button class="copy-btn" data-copy-target="promptbody">Copy prompt</button>
      <span class="prompt-meta">{p['prompt_chars']} chars · {html.escape(p['length_bucket'])}</span>
    </div>
    <pre class="promptbody" id="promptbody">{esc_prompt}</pre>
    {complexity_html}

    <h2 class="sub">The loop</h2>
    {loop_steps_html(p['loop'])}
    <h2 class="sub">Stop condition <span class="muted">(halts on the first that trips)</span></h2>
    {stop_arms_html(p['stop_arms'])}
    <h2 class="sub">Model routing</h2>
    <p class="model-note">{html.escape(p['model'])}</p>
  </section>

  <section class="tabpanel" data-panel="anatomy">
    <p class="lead">Every prompt in this library shares one shape. The colored blocks below are the
    prompt's own paragraphs, labeled by the role they play in the loop.
    <a href="{prefix}anatomy.html">See the full anatomy →</a></p>
    <div class="anat-legend">
      {"".join(f'<span class="anat-key anat-dot-{k}">{ANAT_LABELS[k]}</span>' for k in ANAT_ORDER)}
    </div>
    {render_anatomy(p['prompt_text'], reveal=True)}
  </section>

  <section class="tabpanel" data-panel="why">
    <p class="lead">Not marketing — mechanism. Each principle below is one this prompt
    <em>actually</em> exhibits, quoted from its own text:</p>
    {why_html}
    <h2 class="sub">This prompt's four exits</h2>
    <p class="lead">It can only end one way — whichever of these trips first:</p>
    {stop_arms_html(p['stop_arms'])}
    <p class="muted">Read the underlying <a href="{prefix}anatomy.html">principles and antipatterns →</a>,
    or look up a term in the <a href="{prefix}glossary.html">glossary →</a></p>
  </section>

  <section class="tabpanel" data-panel="source">
    <dl class="source-dl">
      <dt>Collection</dt><dd>prompt-os loop library — this repository, family <code>{p['family_key']}</code>, prompt #{p['num']}.</dd>
      <dt>Method</dt><dd>Generated by a 32-agent research → adversarial-verify → generate → curate workflow, then human-reviewed.</dd>
      <dt>Original / derived</dt><dd>Original — independently authored loop template, not copied from an external collection.</dd>
      <dt>License</dt><dd>See the repository. Reuse the prompt text freely; keep this provenance note if you republish.</dd>
      <dt>Verifier type</dt><dd>{html.escape(p['verifier_type'])} — {'execution/ground-truth signal' if p['verifier_type']=='mechanical' else 'model/rubric judgment' if p['verifier_type']=='judge' else 'both mechanical and judged signals' if p['verifier_type']=='mixed' else 'not clearly specified'}.</dd>
    </dl>
    {dup_html}
  </section>

  {related_html}
</div>
"""
    return page(f"{p['display_title']} · prompt-os", body, prefix,
                desc=p["when"][:180])


# ---- Home -------------------------------------------------------------------

def hero_ring_svg() -> str:
    """A 6-node loop ring: the circle path draws in, nodes fade, a pulse orbits."""
    cx = cy = 100.0
    r = 72.0
    length = 2 * math.pi * r
    nodes = ""
    for i in range(6):
        a = -math.pi / 2 + i * 2 * math.pi / 6
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        nodes += (f'<g class="hero-node" style="--i:{i}"><circle cx="{x:.1f}" cy="{y:.1f}" r="6"/></g>')
    return (
        f'<svg class="hero-ring" viewBox="0 0 200 200" role="img" '
        f'aria-label="A research loop: research, extract, verify, find gaps, search again, synthesize">'
        f'<circle class="hero-ring-path" cx="{cx}" cy="{cy}" r="{r}" style="--len:{length:.0f}"/>'
        f'{nodes}'
        f'<g class="hero-spin"><circle class="hero-pulse" cx="{cx}" cy="{cy - r:.1f}" r="4.5"/></g>'
        f'</svg>'
    )


def render_home(prompts: list[dict], principles: dict, stats: dict) -> str:
    starters = [p for p in prompts if p["starter"]][:6]
    demo = next((p for p in prompts if p["id"] == "build-verify-1"), prompts[0])
    stat_cells = [
        (stats["total"], "verified prompts"), (stats.get("generated_pages", 0), "generated pages"),
        (stats["principle_sets"], "principle combinations"), (stats["families"], "prompt families"),
        (stats["research_loop"], "research-loop prompts"), (stats["anti_oscillation"], "anti-oscillation prompts"),
        (stats["validation_types"], "validation types"), (stats["automation_workflows"], "automation workflows"),
    ]
    stats_html = "".join(
        f'<div class="stat reveal"><span class="stat-n" data-target="{v}">{v}</span>'
        f'<span class="stat-l">{html.escape(l)}</span></div>'
        for v, l in stat_cells
    )
    fam_cards = "".join(
        f'<a class="fam-card" href="family/{k}.html"><span class="fam-name">{html.escape(t)}</span>'
        f'<span class="fam-count">{sum(1 for p in prompts if p["family_key"]==k)} prompts</span></a>'
        for k, t in FAMILIES
    )
    starter_cards = "".join(
        f'<a class="pcard" href="prompt/{p["id"]}.html">'
        f'<span class="pcard-fam">{html.escape(p["family_title"])}</span>'
        f'{card_title_html(p)}'
        f'<span class="pcard-when">{html.escape(p["when"][:120])}…</span>'
        f'<span class="pcard-foot">{facet_chips(p)}</span></a>'
        for p in starters
    )
    body = f"""
<section class="hero">
  <div class="wrap">
    <p class="kicker">prompt-os · loop-prompt library</p>
    <h1>Understand how powerful AI prompts <span class="hl-hand">actually work</span>.</h1>
    <p class="sub">Explore {stats['total']} verified prompts — their internal anatomy, validation
    systems, loops, stopping conditions, and automation patterns. Every one is a
    <em>frozen goal → one action → independent verifier → multi-armed stop</em>.</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="library.html">Explore the library</a>
      <a class="btn btn-ghost" href="loops.html">Watch a loop run</a>
    </div>

    <div class="hero-anim" id="heroAnim">
      <div class="hero-typed" data-text="Research this topic and build the best solution.">Research this topic and build the best solution.</div>
      <div class="hero-chips" aria-hidden="true">
        <span class="hero-chip c-goal" style="--i:0">Goal</span>
        <span class="hero-chip c-context" style="--i:1">Context</span>
        <span class="hero-chip c-process" style="--i:2">Process</span>
        <span class="hero-chip c-verifier" style="--i:3">Verifier</span>
        <span class="hero-chip c-stop" style="--i:4">Exit</span>
      </div>
      {hero_ring_svg()}
      <div class="hero-cap">Research → Extract → Verify → Find gaps → Search again → Synthesize</div>
      <button class="hero-replay" hidden>↻ Replay</button>
    </div>
  </div>
</section>

<section class="wrap statband-wrap">
  <div class="statband">{stats_html}</div>
  <p class="statband-note">Not a store — an analysis. Every number is computed from the corpus by
  <code>build_site.py</code>, not hand-entered. <strong>Verified prompts and automation workflows are
  counted separately</strong>, never merged into one inflated total.
  <a class="inline-link" href="patterns.html">Browse the patterns →</a></p>
</section>

<section class="wrap demo">
  <h2 class="section-h">One prompt, decomposed</h2>
  <p class="section-sub">This is a real prompt from the library. Each colored block is the role it plays in the loop.</p>
  <div class="anat-legend">
    {"".join(f'<span class="anat-key anat-dot-{k}">{ANAT_LABELS[k]}</span>' for k in ANAT_ORDER)}
  </div>
  <div class="demo-box">
    {render_anatomy(demo['prompt_text'])}
  </div>
  <p><a class="inline-link" href="prompt/{demo['id']}.html">Open “{html.escape(demo['display_title'])}” →</a></p>
</section>

<section class="wrap">
  <h2 class="section-h">Start here</h2>
  <p class="section-sub">The most broadly useful prompts, from the library's own curation.</p>
  <div class="pcard-grid">{starter_cards}</div>
</section>

<section class="wrap">
  <h2 class="section-h">Browse by family</h2>
  <div class="fam-grid">{fam_cards}</div>
</section>

<section class="wrap principles-teaser">
  <h2 class="section-h">The one idea</h2>
  <blockquote>{html.escape(principles['intro'])}</blockquote>
  <a class="inline-link" href="anatomy.html">The 11 principles &amp; the antipatterns that break loops →</a>
</section>
"""
    return page("prompt-os · loop-prompt library", body, "",
                desc="112 agent-loop prompts across 14 families, each with an explicit stop condition. "
                     "Learn the anatomy of reliable AI loops.")


# ---- Pattern explorer -------------------------------------------------------

def render_patterns_index(stats: dict, pat_docs: dict) -> str:
    counts = stats["pattern_counts"]
    rows = []
    for k, name, role, blurb in PATTERN_META:
        c = counts.get(k, 0)
        doc = pat_docs.get(k, {})
        desc = doc.get("definition") or blurb
        dot = f'<span class="gloss-dot anat-dot-{role}"></span>' if role else ""
        rows.append(
            f'<a class="pat-card" href="pattern/{k}.html">'
            f'<span class="pat-head">{dot}<span class="pat-name">{html.escape(name)}</span>'
            f'<span class="pat-count">{c}</span></span>'
            f'<span class="pat-desc">{html.escape(desc[:150])}</span></a>'
        )
    body = f"""
<section class="wrap">
  <h1 class="section-h">Pattern explorer</h1>
  <p class="section-sub">The reusable structures underneath the 112 prompts — detected mechanically,
  counted across the whole corpus. The number is how many prompts use each.</p>
  <div class="pat-grid">{"".join(rows)}</div>
</section>
"""
    return page("Patterns · prompt-os", body, "",
                desc="The reusable loop patterns across the prompt-os corpus, with usage counts — "
                     "commit/revert, human escalation, adversarial verification, fan-out, ratchet, and more.")


def render_pattern_page(key: str, name: str, role: str | None, blurb: str,
                        prompts: list[dict], doc: dict) -> str:
    prefix = "../"
    users = [p for p in prompts if key in detect_patterns(p)]
    fams = {}
    for p in users:
        fams.setdefault(p["family_key"], []).append(p)
    cards = "".join(
        f'<a class="pcard" href="{prefix}prompt/{p["id"]}.html">'
        f'<span class="pcard-fam">{html.escape(p["family_title"])}</span>'
        f'{card_title_html(p)}'
        f'<span class="pcard-foot">{facet_chips(p)}</span></a>'
        for p in users
    )
    definition = doc.get("definition") or blurb
    ideal = doc.get("ideal_use")
    poor = doc.get("poor_use")
    failures = doc.get("failure_modes") or []
    dot = f'<span class="gloss-dot anat-dot-{role}"></span>' if role else ""

    extra = ""
    if ideal or poor or failures:
        blocks = ""
        if ideal:
            blocks += f'<div class="pat-block"><h3>Ideal use</h3><p>{html.escape(ideal)}</p></div>'
        if poor:
            blocks += f'<div class="pat-block"><h3>Poor fit</h3><p>{html.escape(poor)}</p></div>'
        if failures:
            items = "".join(f"<li>{html.escape(f)}</li>" for f in failures)
            blocks += f'<div class="pat-block"><h3>Failure modes</h3><ul>{items}</ul></div>'
        extra = f'<div class="pat-blocks">{blocks}</div>'

    body = f"""
<section class="wrap pattern-page">
  <p class="crumbs"><a href="{prefix}patterns.html">Patterns</a> › <span>{html.escape(name)}</span></p>
  <h1 class="section-h">{dot}{html.escape(name)}</h1>
  <p class="lead big">{html.escape(definition)}</p>
  {extra}
  <h2 class="section-h">Used by {len(users)} prompt{"s" if len(users) != 1 else ""}
    <span class="muted">across {len(fams)} famil{"ies" if len(fams) != 1 else "y"}</span></h2>
  <div class="pcard-grid">{cards}</div>
</section>
"""
    return page(f"{name} · Patterns · prompt-os", body, prefix,
                desc=definition[:180])


# ---- Loop visualizer --------------------------------------------------------

LOOPVIZ_PRESETS = [
    ("research", "Research loop", "research-until-dry-1"),
    ("coding", "Coding loop", "build-verify-1"),
    ("prompt", "Prompt-improvement loop", "prompt-optimization-1"),
    ("debug", "Debugging loop", "debug-rootcause-1"),
]


def _loop_label(text: str) -> str:
    words = re.sub(r"[^\w\s-]", "", text).split()
    skip = {"the", "a", "an", "to", "and", "of", "for"}
    words = [w for w in words if w.lower() not in skip] or text.split()
    lab = words[0]
    if len(lab) < 5 and len(words) > 1:
        lab = lab + " " + words[1]
    return lab[:12].strip().capitalize()


def build_loopviz(prompts: list[dict]) -> dict:
    by_id = {p["id"]: p for p in prompts}
    data = {}
    for key, name, pid in LOOPVIZ_PRESETS:
        p = by_id.get(pid)
        if not p:
            continue
        raw = [s.strip() for s in re.split(r"\s*->\s*|\s*→\s*", p["loop"]) if s.strip()]
        steps = [{"label": _loop_label(s), "desc": s[0].upper() + s[1:]} for s in raw]
        if steps:
            steps[0]["quote"] = "Goal: " + (p["when"][:150])
        data[key] = {"name": name, "prompt_id": pid, "title": p["display_title"],
                     "steps": steps, "exits": p["stop_arms"]}
    return data


def render_loops(prompts: list[dict]) -> str:
    viz = build_loopviz(prompts)
    first = LOOPVIZ_PRESETS[0][0]
    presets = "".join(
        f'<button class="lv-preset{" active" if k == first else ""}" data-k="{k}">{html.escape(nm)}</button>'
        for k, nm, _ in LOOPVIZ_PRESETS if k in viz
    )
    fallback = "".join(f"<li><strong>{html.escape(s['label'])}</strong> — {html.escape(s['desc'])}</li>"
                       for s in viz[first]["steps"])
    body = f"""
<section class="wrap loopviz-page" id="loopviz">
  <h1 class="section-h">Loop visualizer</h1>
  <p class="section-sub">Advanced AI systems aren't one giant prompt — they're a controlled loop of small
  model calls. Step through a real loop from the library and watch where it can exit. Data is the actual
  <code>loop</code> and stop condition of each prompt.</p>

  <div class="lv-presets">{presets}</div>

  <div class="loopviz" tabindex="0" aria-label="Interactive loop, use arrow keys to step">
    <div class="lv-stage">
      <div class="lv-ring-wrap"></div>
      <div class="lv-panel">
        <div class="lv-step-label">Step</div>
        <div class="lv-step-title">—</div>
        <div class="lv-step-desc"></div>
        <div class="lv-quote" hidden></div>
        <div class="lv-exits"></div>
        <p class="muted" style="margin-top:14px;font-size:.82rem">Exit conditions halt the loop on the first that trips — click one to fire it.</p>
      </div>
    </div>
    <div class="lv-controls">
      <button class="lv-btn primary lv-play">▶ Play</button>
      <button class="lv-btn lv-prev">‹ Prev</button>
      <button class="lv-btn lv-next">Next ›</button>
      <button class="lv-btn lv-restart">↻ Restart</button>
      <button class="lv-btn lv-speed">1×</button>
    </div>
    <ol class="lv-fallback">{fallback}</ol>
  </div>
</section>
<script>window.LOOPVIZ = {json.dumps(viz, ensure_ascii=False)};</script>
"""
    return page("Loops · prompt-os", body, "",
                desc="Interactive loop visualizer — step through real agent loops (research, coding, "
                     "prompt-improvement, debugging) and see their SUCCESS/BUDGET/NO-PROGRESS/BLOCKED exits.")


# ---- Constellation graph ----------------------------------------------------

def build_graph_data(prompts: list[dict], related: dict) -> dict:
    """Nodes = prompts; edges = real relationships (curation near-dups + shared patterns).
    Positions are computed deterministically in JS from the family index (no physics sim)."""
    idx = {p["id"]: i for i, p in enumerate(prompts)}
    fam_keys = [k for k, _ in FAMILIES]
    fam_i = {k: i for i, k in enumerate(fam_keys)}
    nodes = [{
        "t": p["display_title"], "f": fam_i[p["family_key"]],
        "fk": p["family_key"], "id": p["id"],
        "p": [k for k, _n, _r, _b in PATTERN_META if k in detect_patterns(p)],
    } for p in prompts]
    seen = set()
    edges = []
    for p in prompts:
        for q, _sh, cur in related.get(p["id"], []):
            a, b = idx[p["id"]], idx[q["id"]]
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"s": key[0], "t": key[1], "c": 1 if cur else 0})
    return {"nodes": nodes, "edges": edges,
            "families": [{"key": k, "title": t} for k, t in FAMILIES]}


def render_graph(prompts: list[dict], related: dict) -> str:
    data = build_graph_data(prompts, related)
    fam_opts = "".join(f'<option value="{k}">{html.escape(t)}</option>' for k, t in FAMILIES)
    # no-JS fallback: a plain family→prompt list so content exists without the graph
    fallback = ""
    for k, t in FAMILIES:
        items = "".join(f'<li><a href="prompt/{p["id"]}.html">{html.escape(p["display_title"])}</a></li>'
                        for p in prompts if p["family_key"] == k)
        fallback += f"<details><summary>{html.escape(t)}</summary><ul>{items}</ul></details>"
    body = f"""
<section class="wrap graph-page">
  <h1 class="section-h">Prompt constellation</h1>
  <p class="section-sub">Every prompt is a node, clustered by family. Lines are <em>real</em> relationships —
  ★ near-duplicates from the library's own curation notes, plus shared patterns. Hover a node to light up its
  relatives; click to open it. Not decoration: no edge exists that isn't in the data.</p>
  <div class="graph-controls">
    <select id="g-family" class="filter"><option value="">All families</option>{fam_opts}</select>
    <button class="lv-btn" id="g-reset">Reset</button>
    <span class="graph-hint muted">Tip: hover = highlight relatives · click = open</span>
  </div>
  <div class="graph-stage">
    <div class="graph-wrap" id="graphWrap" role="img" aria-label="Constellation of {len(data['nodes'])} prompts clustered by family"></div>
    <aside class="graph-panel" id="graphPanel" hidden></aside>
  </div>
  <details class="graph-fallback"><summary>Browse as a list instead</summary>{fallback}</details>
</section>
<script>window.GRAPH = {json.dumps(data, ensure_ascii=False)};</script>
"""
    return page("Constellation · prompt-os", body, "",
                desc="An interactive constellation of every prompt, clustered by family, with real "
                     "relationship edges from shared patterns and curation near-duplicates.")


# ---- Automation section -----------------------------------------------------

def _step_counts(a: dict) -> tuple[int, int, int]:
    ai = sum(1 for t, _ in a["steps"] if t == "ai")
    det = sum(1 for t, _ in a["steps"] if t in ("deterministic", "validation", "store"))
    hum = sum(1 for t, _ in a["steps"] if t == "human")
    return ai, det, hum


def render_automation_index() -> str:
    by_cat = {}
    for a in AUTOMATIONS:
        by_cat.setdefault(a["category"], []).append(a)
    secs = ""
    for cat in AUTOMATION_CATEGORIES:
        cards = ""
        for a in by_cat[cat]:
            ai, det, hum = _step_counts(a)
            cards += (
                f'<a class="auto-card" href="automation/{a["key"]}.html">'
                f'<span class="auto-name">{html.escape(a["name"])}</span>'
                f'<span class="auto-flow">'
                + "".join(f'<span class="stepdot {STEP_LABELS[t][1]}" title="{STEP_LABELS[t][0]}"></span>'
                          for t, _ in a["steps"]) +
                f'</span>'
                f'<span class="auto-meta">{ai} AI · {det} deterministic · {hum} human · {html.escape(a["schedule"])}</span>'
                f'</a>'
            )
        secs += f'<section class="auto-cat"><h2 class="section-h">{html.escape(cat)}</h2><div class="auto-grid">{cards}</div></section>'
    legend = "".join(
        f'<span class="step-key"><span class="stepdot {cls}"></span>{html.escape(lbl)}</span>'
        for lbl, cls in STEP_LABELS.values()
    )
    body = f"""
<section class="wrap automation">
  <h1 class="section-h">Automation library</h1>
  <p class="section-sub">Illustrative AI-in-the-loop workflows. The point isn't the tool — it's the
  <strong>shape</strong>: which steps genuinely need a model, which must stay deterministic, and where a
  human or a validator gates the flow. Reference patterns, not scraped or benchmarked templates.</p>
  <div class="step-legend">{legend}</div>
  {secs}
  <p class="muted" style="margin-top:32px">Every workflow here separates the <span class="step-key"><span class="stepdot step-ai"></span>AI decision</span>
  from the <span class="step-key"><span class="stepdot step-det"></span>deterministic</span> plumbing —
  the single thing most “AI automation” gets wrong. See how the same discipline runs inside a single prompt on the
  <a href="anatomy.html">anatomy page</a>.</p>
</section>
"""
    return page("Automation · prompt-os", body, "",
                desc="Illustrative AI-in-the-loop automation workflows, every step typed AI vs deterministic "
                     "vs human-approval, with reliability controls — inbox triage, research digest, doc extraction, "
                     "anomaly alerting, and more.")


def render_automation_page(a: dict, doc: dict) -> str:
    prefix = "../"
    goal = doc.get("goal") or f"An automation that runs on {a['schedule']}."
    why_ai = doc.get("why_ai")
    failures = doc.get("failure_modes") or []
    reliability = doc.get("reliability") or []

    flow = ""
    for i, (t, text) in enumerate(a["steps"]):
        lbl, cls = STEP_LABELS[t]
        flow += (
            f'<div class="flow-step">'
            f'<span class="flow-badge {cls}">{html.escape(lbl)}</span>'
            f'<span class="flow-text">{html.escape(text)}</span></div>'
        )
        if i < len(a["steps"]) - 1:
            flow += '<div class="flow-arrow">↓</div>'

    rel_html = ""
    if reliability:
        rel_html = "<ul class='rel-list'>" + "".join(f"<li>{html.escape(r)}</li>" for r in reliability) + "</ul>"
    else:
        rel_html = (f'<ul class="rel-list"><li><strong>Retry:</strong> {html.escape(a["retry"])}</li>'
                    f'<li><strong>Human gate:</strong> a person approves before any irreversible or public step.</li>'
                    f'<li><strong>Fallback:</strong> low-confidence work is routed to review, never auto-committed.</li></ul>')
    fail_html = ""
    if failures:
        fail_html = ("<h2 class='section-h'>Failure modes</h2><ul class='fail-list'>"
                     + "".join(f"<li>{html.escape(f)}</li>" for f in failures) + "</ul>")

    why_ai_html = f'<p class="why-ai"><strong>Why a model, not just code:</strong> {html.escape(why_ai)}</p>' if why_ai else ""
    ai, det, hum = _step_counts(a)
    body = f"""
<section class="wrap automation-page">
  <p class="crumbs"><a href="{prefix}automation.html">Automation</a> › <span>{html.escape(a["name"])}</span></p>
  <h1 class="section-h">{html.escape(a["name"])}</h1>
  <p class="lead big">{html.escape(goal)}</p>
  <div class="auto-facts">
    <span class="chip chip-family">{html.escape(a["category"])}</span>
    <span class="chip">{html.escape(a["schedule"])}</span>
    <span class="chip">{ai} AI · {det} deterministic · {hum} human</span>
  </div>
  {why_ai_html}

  <h2 class="section-h">The workflow</h2>
  <p class="section-sub">Each step is typed. Notice how few steps actually need the model.</p>
  <div class="auto-run">
    <button class="lv-btn primary" id="autoRun">▶ Run once</button>
    <label class="muted" for="autoCond" style="font-size:.85rem">Simulate:</label>
    <select id="autoCond">
      <option value="success">Success</option>
      <option value="low-confidence">Low confidence</option>
      <option value="invalid-output">Invalid AI output</option>
      <option value="api-timeout">API timeout</option>
      <option value="human-reject">Human rejects</option>
    </select>
  </div>
  <div class="run-status" id="autoStatus" aria-live="polite"></div>
  <div class="flow" data-run>{flow}</div>

  <h2 class="section-h">Reliability</h2>
  {rel_html}

  {fail_html}

  <p class="muted">This is a reference shape to adapt, not a drop-in template — wire it to your own
  tools, and keep the human/validation gates where money or irreversible actions are involved.</p>
</section>
"""
    return page(f"{a['name']} · Automation · prompt-os", body, prefix, desc=goal[:180])


# ---- Library ----------------------------------------------------------------

def render_library() -> str:
    fam_opts = "".join(f'<option value="{k}">{html.escape(t)}</option>' for k, t in FAMILIES)
    body = f"""
<section class="wrap lib">
  <h1 class="section-h">Prompt library</h1>
  <p class="section-sub">All 112 loop prompts. Filter and search — everything runs in your browser.</p>

  <div class="lib-controls">
    <input id="q" class="search" type="search" placeholder="Search title, purpose, or prompt text…" autocomplete="off">
    <select id="f-family" class="filter"><option value="">All families</option>{fam_opts}</select>
    <select id="f-verifier" class="filter">
      <option value="">Any verifier</option>
      <option value="mechanical">Mechanical (execution)</option>
      <option value="judge">Judge (rubric/model)</option>
      <option value="mixed">Mixed</option>
    </select>
    <select id="f-model" class="filter">
      <option value="">Any model tier</option>
      <option value="cheap">Cheaper is fine</option>
      <option value="escalate">Start cheap, escalate</option>
      <option value="top-tier">Top-tier</option>
    </select>
    <label class="toggle"><input type="checkbox" id="f-starter"> Starter set only</label>
  </div>
  <p id="count" class="lib-count"></p>
  <div id="results" class="pcard-grid"></div>
  <p id="empty" class="empty" hidden>No prompts match. Clear a filter.</p>
</section>
"""
    return page("Library · prompt-os", body, "",
                desc="Searchable library of 112 agent-loop prompts.",
                extra_head='<link rel="preload" href="data/prompts.json" as="fetch" crossorigin>')


# ---- Anatomy ----------------------------------------------------------------

def render_anatomy_page(principles: dict, prompts: list[dict]) -> str:
    demo = next((p for p in prompts if p["id"] == "research-until-dry-1"), prompts[0])
    comp_rows = "".join(
        f'<div class="comp comp-{k}"><span class="anat-label">{ANAT_LABELS[k]}</span>'
        f'<p>{html.escape(desc)}</p></div>'
        for k, desc in [
            ("goal", "A mechanically-checkable exit target, frozen at loop start so “done” never drifts."),
            ("verifier", "An independent signal — test suite, benchmark, schema, adversarial check — decides “done”, not the model's own confidence."),
            ("action", "The smallest coherent change, then one verification — regressions stay attributable and reversible."),
            ("state", "A compact scratchpad carried forward (goal, tried, best, budget), not the whole transcript."),
            ("stop", "Every exit enumerated up front; halt on the FIRST of SUCCESS / BUDGET / NO-PROGRESS / BLOCKED."),
        ]
    )
    principle_html = "".join(
        f'<div class="principle"><h3>{html.escape(pr["name"])}</h3><p>{html.escape(pr["body"])}</p></div>'
        for pr in principles["principles"]
    )
    anti_html = "".join(f"<li>{html.escape(a)}</li>" for a in principles["antipatterns"])
    body = f"""
<section class="wrap anat-page">
  <h1 class="section-h">The anatomy of a loop</h1>
  <p class="lead big">{html.escape(principles['intro'])}</p>

  <h2 class="section-h">Four parts, always present</h2>
  <div class="comp-grid">{comp_rows}</div>

  <h2 class="section-h">Seen in a real prompt</h2>
  <div class="anat-legend">
    {"".join(f'<span class="anat-key anat-dot-{k}">{ANAT_LABELS[k]}</span>' for k in ANAT_ORDER)}
  </div>
  <div class="demo-box">{render_anatomy(demo['prompt_text'])}</div>
  <p><a class="inline-link" href="prompt/{demo['id']}.html">Open “{html.escape(demo['display_title'])}” →</a></p>

  <h2 class="section-h">The 11 principles</h2>
  <div class="principles">{principle_html}</div>

  <h2 class="section-h">Antipatterns — what makes a loop fail</h2>
  <ul class="anti">{anti_html}</ul>
</section>
"""
    return page("Anatomy · prompt-os", body, "",
                desc="The universal anatomy of a reliable agent loop: frozen goal, one action, "
                     "independent verifier, multi-armed stop — plus 11 principles and the antipatterns.")


# ---- Family page ------------------------------------------------------------

def render_family(key: str, title: str, prompts: list[dict]) -> str:
    prefix = "../"
    fam = [p for p in prompts if p["family_key"] == key]
    cards = "".join(
        f'<a class="pcard" href="{prefix}prompt/{p["id"]}.html">'
        f'{card_title_html(p, num=True)}'
        f'<span class="pcard-when">{html.escape(p["when"][:140])}…</span>'
        f'<span class="pcard-foot">{facet_chips(p)}</span></a>'
        for p in fam
    )
    dup = parse_curation_note(key)
    dup_html = ""
    if dup:
        dup_html = ("<section class='dup-section'><h2 class='sub'>Near-duplicates elsewhere in the library</h2>"
                    "<p class='muted'>Kept on purpose: the same loop recurring under a new framing is itself a lesson.</p>"
                    "<ul class='dup-list'>"
                    + "".join(f"<li>{html.escape(l)}</li>" for l in dup.splitlines()) + "</ul></section>")
    body = f"""
<section class="wrap family">
  <p class="crumbs"><a href="{prefix}library.html">Library</a> › <span>{html.escape(title)}</span></p>
  <h1 class="section-h">{html.escape(title)}</h1>
  <p class="section-sub">{len(fam)} loop prompts in this family.</p>
  <div class="pcard-grid">{cards}</div>
  {dup_html}
</section>
"""
    return page(f"{title} · prompt-os", body, prefix,
                desc=f"{len(fam)} {title} loop prompts.")


# ---- Glossary + Families index ---------------------------------------------

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# Every term below is used somewhere in the 112 prompts. Definitions are authored
# here (mechanism-focused, grounded in loops/00-loop-engineering-principles.md);
# `role` draws the matching anatomy colour dot where one applies.
GLOSSARY = [
    ("Loop anatomy", [
        ("Agent loop", None, "Turning an open-ended task into a bounded control loop: a frozen goal, small reversible steps, an independent verifier, and an explicit multi-armed stop — instead of one big one-shot prompt."),
        ("Frozen goal", "goal", "A mechanically-checkable exit target, fixed at loop start so “done” means the same thing on turn 1 and turn 20. Freezing it is what prevents goalpost-moving."),
        ("One reversible action per turn", "action", "Each iteration is the smallest coherent change plus a single verification, so any regression is attributable to exactly one action and can be rolled back cleanly."),
        ("Independent verifier", "verifier", "The mechanism that decides “done” is different from the thing being optimized — compiler, test suite, benchmark, schema validator, adversarial check — never the model’s own confidence."),
        ("Compact state (scratchpad)", "state", "The distilled running state carried across turns — goal, what’s been tried, current best, last verifier result, remaining budget — fed forward instead of the whole transcript."),
        ("Multi-armed stop", "stop", "The loop halts on the FIRST of several enumerated exits, not only on success. A stop with only a success arm is an infinite loop waiting to happen."),
        ("SUCCESS", "stop", "Stop arm: the goal is met and has been independently verified."),
        ("BUDGET", "stop", "Stop arm: the max iterations / tokens / wall-clock ceiling has been reached."),
        ("NO-PROGRESS", "stop", "Stop arm: the target metric hasn’t improved for K turns — halt or change strategy rather than grind."),
        ("BLOCKED", "stop", "Stop arm: the loop needs human input or an unavailable resource; surface it and hand off."),
        ("Known-good invariant", None, "End every turn in a state you’d be willing to keep (compiles, tests green): commit on improvement, <code>git reset</code> on regression, so one bad turn can’t corrupt the baseline."),
    ]),
    ("Failure modes", [
        ("Oscillation", None, "The agent flips A→B→A between two states while reporting progress; a reliable loop detects the cycle and forces a strategy change."),
        ("No-progress / plateau", None, "The metric flatlines for K turns or sits inside a noise band; keep looping and you burn budget for nothing."),
        ("Goodhart’s law", None, "Verifying with the exact signal you optimized against — the metric stops measuring the goal once it becomes the target. Verify with a signal distinct from the one you tuned."),
        ("Scope creep / gold-plating", None, "Adding features or edge cases discovered mid-loop instead of parking them; the loop closes the defined gap and nothing else."),
        ("Goalpost-moving", None, "Redefining success downward to declare victory when the real criterion won’t be met."),
        ("Self-grading", None, "The agent that produced the output also declares it correct, with no independent verifier or ground truth."),
        ("Context bloat", None, "Passing the full raw transcript every turn instead of compact state, causing drift and lost budget."),
        ("Escalation (fail loud)", None, "After the same step fails ~3 times, stop, surface the concrete error plus everything already tried, and hand off — cheaper and safer than grinding the budget."),
    ]),
    ("Verification & judging", [
        ("Actor / verifier / judge separation", None, "Run the critique in a fresh frame or a distinct role so it doesn’t inherit the author’s blind spots; the refiner acts only on concrete verifier findings, not its own re-reading."),
        ("Adversarial verification (red-team)", None, "A claim or finding counts only if it survives an independent attempt to refute it against an independent source."),
        ("Mechanical verifier", None, "An execution / ground-truth signal — test suite, benchmark, schema validator, compiler, scanner. The strongest kind of verifier."),
        ("Judge / rubric", None, "A model or scoring rubric used where there is no ground truth (copy quality, tone, policy). Weaker than mechanical; define the rubric before the loop starts."),
        ("pass@1", None, "Functional-correctness metric: does the generated code pass the frozen test suite on the first accepted attempt."),
        ("Saturation (“dry”)", None, "A research loop’s stop signal: new sources and searches stop changing the answer and corroboration converges — evidence-saturated, not effort-exhausted."),
    ]),
    ("Family techniques", [
        ("Characterization test", None, "A test that pins down the existing (even buggy) behavior of untested legacy code before a refactor, so the change provably preserves behavior."),
        ("Ratchet (ratcheting strictness)", None, "A per-file or per-metric counter that may only move toward the target (e.g. type errors down), never backward — the engine of a gradual migration."),
        ("Expand → migrate → contract", None, "A safe schema-change sequence: add the new shape, move readers/writers across with shadow verification, then remove the old shape."),
        ("Shadow read / verify", None, "Running the new path alongside the old and comparing outputs before cutting over."),
        ("Codemod / worklist", None, "A frozen list of call-sites to transform identically; the loop closes the worklist without re-scoping mid-run."),
        ("Fan-out / pipeline", None, "Orchestration patterns: fan-out runs N subagents in parallel on independent items; a pipeline routes each item through fixed stages. Reach for them only after the single-thread loop works."),
        ("Minimal-with-strong-heuristics", None, "Keep the loop control rigid (one action, verify, check every stop arm) but leave the model’s judgment about which action minimally prescribed — over-scripted mega-prompts degrade frontier models."),
    ]),
]


def render_glossary() -> str:
    secs = []
    for title, terms in GLOSSARY:
        rows = []
        for term, role, desc in terms:
            dot = f'<span class="gloss-dot anat-dot-{role}"></span>' if role else ""
            rows.append(
                f'<div class="gterm" id="{slug(term)}">'
                f'<dt>{dot}{html.escape(term)}</dt><dd>{desc}</dd></div>'
            )
        secs.append(
            f'<section class="gsec"><h2 class="section-h">{html.escape(title)}</h2>'
            f'<dl class="glist">{"".join(rows)}</dl></section>'
        )
    body = f"""
<section class="wrap glossary">
  <h1 class="section-h">Glossary</h1>
  <p class="section-sub">The vocabulary of reliable agent loops. Every term here is used somewhere
  in the 112 prompts — coloured dots map to the <a href="anatomy.html">loop anatomy</a>.</p>
  {"".join(secs)}
</section>
"""
    return page("Glossary · prompt-os", body, "",
                desc="A glossary of agent-loop and prompt-engineering terms — frozen goal, "
                     "independent verifier, multi-armed stop, Goodhart, ratchet, saturation, and more.")


def render_families_index(prompts: list[dict]) -> str:
    cards = "".join(
        f'<a class="fam-lg" href="family/{k}.html">'
        f'<span class="fam-lg-head"><span class="fam-name">{html.escape(t)}</span>'
        f'<span class="fam-count">{sum(1 for p in prompts if p["family_key"]==k)} prompts</span></span>'
        f'<span class="fam-desc">{html.escape(family_desc(k, t))}</span></a>'
        for k, t in FAMILIES
    )
    body = f"""
<section class="wrap">
  <h1 class="section-h">The 14 loop families</h1>
  <p class="section-sub">Every family is the same meta-shape — frozen goal → one action → independent
  verifier → multi-armed stop — specialized to a kind of work. The original families have 8 prompts each;
  newer ones (image generation, RAG, browser agents) are still growing.</p>
  <div class="fam-lg-grid">{cards}</div>
</section>
"""
    return page("Families · prompt-os", body, "",
                desc="The 14 agent-loop families in prompt-os — build, debug, red-team, refactor, "
                     "research, planning, testing, review, self-critique, migration, eval, orchestration, "
                     "prompt-optimization, data-pipeline.")


# ----------------------------------------------------------------------------
# CSS + JS
# ----------------------------------------------------------------------------

CSS = r""":root{
  --bg:#f6f0e5; --panel:#fffdf8; --ink:#2a2420; --ink-soft:#585046; --muted:#8a8072;
  --line:#e9dfcc; --line-strong:#dccfb6; --accent:#3a4ce0; --accent-ink:#2733a8;
  --warm:#c26a43; --warm-ink:#a2512f;
  --shadow:0 1px 2px rgba(120,90,50,.05), 0 8px 24px -12px rgba(120,90,50,.12);
  --code-bg:#f3ecdd; --code-ink:#2a2622;
  --goal:#1f7a5a; --goal-bg:#e7f4ee; --verifier:#0f7f80; --verifier-bg:#e0f2f1;
  --action:#2f6fd0; --action-bg:#e8f0fb;
  --state:#8a6d1f; --state-bg:#f6efdc; --stop:#b0472b; --stop-bg:#fbeae4; --context:#6a6a6a; --context-bg:#f1efe9;
  --success:#1f7a5a; --budget:#8a6d1f; --noprogress:#7a5cc0; --blocked:#b0472b;
  --radius:13px; --wrap:1120px;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
  /* motion tokens */
  --dur-instant:100ms; --dur-fast:190ms; --dur-standard:320ms; --dur-explain:700ms; --dur-cine:2000ms;
  --ease-entrance:cubic-bezier(.2,.7,.2,1); --ease-exit:cubic-bezier(.4,0,1,1);
  --ease-spring:cubic-bezier(.34,1.4,.64,1); --ease-linear:linear;
  --move-1:4px; --move-2:8px; --move-3:16px; --move-4:24px;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#1a1712; --panel:#221e17; --ink:#efe8dc; --ink-soft:#cabfad; --muted:#9c917f;
  --line:#332d22; --line-strong:#43392b; --accent:#8b96ff; --accent-ink:#aab2ff;
  --warm:#e08a5e; --warm-ink:#e8a078;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px -12px rgba(0,0,0,.5);
  --code-bg:#251f16; --code-ink:#e8e1d4;
  --goal:#57c79b; --goal-bg:#12261f; --verifier:#4fc9c8; --verifier-bg:#0e2626;
  --action:#78a9f0; --action-bg:#141f30;
  --state:#d8b45a; --state-bg:#2a2312; --stop:#e8896e; --stop-bg:#2c1712;
  --context:#a5a4ae; --context-bg:#232229;
  --success:#57c79b; --budget:#d8b45a; --noprogress:#b4a2ee; --blocked:#e8896e;
}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:var(--sans);background:var(--bg);color:var(--ink);
  line-height:1.6;-webkit-font-smoothing:antialiased;font-size:16px}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 24px}
a{color:var(--accent-ink);text-decoration:none}
a:hover{text-decoration:underline}
.skip{position:absolute;left:-999px}
.skip:focus{left:8px;top:8px;background:var(--panel);padding:8px 12px;z-index:99;border:1px solid var(--line)}
code{font-family:var(--mono);background:var(--code-bg);color:var(--code-ink);
  padding:.1em .35em;border-radius:5px;font-size:.9em}
.muted{color:var(--muted)}

/* header/footer */
.site-head{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:saturate(1.4) blur(8px);border-bottom:1px solid var(--line)}
.head-inner{display:flex;align-items:center;justify-content:space-between;height:60px}
.brand{font-weight:700;font-size:1.15rem;color:var(--ink);letter-spacing:-.02em}
.brand span{color:var(--warm)}
.site-head nav{display:flex;gap:22px}
.site-head nav a{color:var(--ink-soft);font-weight:500;font-size:.95rem}
.site-head nav a:hover{color:var(--accent-ink);text-decoration:none}
.site-foot{border-top:1px solid var(--line);margin-top:64px;padding:32px 0;color:var(--ink-soft);font-size:.9rem}
.site-foot p{margin:.4em 0;max-width:70ch}

/* hero */
.hero{padding:72px 0 40px;border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 6%,var(--bg)),var(--bg))}
.kicker{font-family:var(--mono);font-size:.8rem;text-transform:uppercase;letter-spacing:.12em;
  color:var(--warm-ink);margin:0 0 12px}
/* hand-drawn wavy underline — theme-adaptive, no web font needed */
.hl-hand{text-decoration:underline;text-decoration-color:var(--warm);text-decoration-style:wavy;
  text-decoration-thickness:2px;text-underline-offset:6px}
.hero h1{font-size:clamp(2rem,4.5vw,3.1rem);line-height:1.12;letter-spacing:-.03em;margin:0 0 16px;max-width:16ch}
.hero .sub{font-size:1.15rem;max-width:60ch;color:var(--ink-soft);margin:0 0 28px}
.hero em{font-style:normal;font-family:var(--mono);font-size:.92em;color:var(--ink)}
.cta-row{display:flex;gap:14px;flex-wrap:wrap}
.btn{display:inline-block;padding:12px 22px;border-radius:var(--radius);font-weight:600;font-size:.98rem;border:1px solid transparent}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-ink);text-decoration:none}
.btn-ghost{border-color:var(--line-strong);color:var(--ink)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent-ink);text-decoration:none}

/* sections */
.section-h{font-size:1.5rem;letter-spacing:-.02em;margin:56px 0 6px}
.hero + .demo .section-h,.wrap > .section-h:first-child{margin-top:40px}
.section-sub{color:var(--ink-soft);margin:0 0 22px}
.lead{color:var(--ink-soft);max-width:70ch}
.lead.big{font-size:1.15rem}
.inline-link{font-weight:600}

/* cards */
.pcard-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.pcard{display:flex;flex-direction:column;gap:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px;transition:border-color .15s,transform .15s}
.pcard:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-2px)}
.pcard-fam{font-family:var(--mono);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--accent-ink)}
.pcard-title{font-weight:650;color:var(--ink);line-height:1.25}
.pcard-alt{font-size:.82rem;color:var(--muted);line-height:1.3;margin-top:-2px}
.pcard-when{font-size:.88rem;color:var(--muted);line-height:1.45}
.pcard-foot{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:6px}

.fam-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.fam-card{display:flex;justify-content:space-between;align-items:center;gap:10px;background:var(--panel);
  border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.fam-card:hover{border-color:var(--accent);text-decoration:none}
.fam-name{font-weight:600;color:var(--ink)}
.fam-count{font-family:var(--mono);font-size:.78rem;color:var(--muted);white-space:nowrap}

/* chips */
.chip{display:inline-block;font-size:.72rem;padding:2px 8px;border-radius:20px;
  border:1px solid var(--line-strong);color:var(--ink-soft);background:var(--panel);white-space:nowrap}
.chip-family{border-color:color-mix(in srgb,var(--accent) 40%,var(--line));color:var(--accent-ink)}
.chip-starter{background:color-mix(in srgb,var(--goal) 14%,var(--panel));border-color:var(--goal);color:var(--goal)}
.chip-mechanical{border-color:var(--action);color:var(--action)}
.chip-judge{border-color:var(--noprogress);color:var(--noprogress)}

/* demo / anatomy blocks */
.anat-legend{display:flex;flex-wrap:wrap;gap:14px;margin:14px 0 18px}
.anat-key{font-size:.8rem;font-weight:600;padding-left:18px;position:relative;color:var(--ink-soft)}
.anat-key::before,.anat-dot::before{content:"";position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:11px;height:11px;border-radius:3px}
.anat-dot{position:relative;padding-left:18px}
.anat-dot-goal::before{background:var(--goal)} .anat-dot-verifier::before{background:var(--verifier)}
.anat-dot-action::before{background:var(--action)}
.anat-dot-state::before{background:var(--state)} .anat-dot-stop::before{background:var(--stop)}
.anat-dot-context::before{background:var(--context)}
.demo-box{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:8px;display:grid;gap:8px}
.anat{border-left:4px solid var(--context);background:var(--context-bg);border-radius:6px;padding:10px 14px}
.anat-goal{border-color:var(--goal);background:var(--goal-bg)}
.anat-verifier{border-color:var(--verifier);background:var(--verifier-bg)}
.anat-action{border-color:var(--action);background:var(--action-bg)}
.anat-state{border-color:var(--state);background:var(--state-bg)}
.anat-stop{border-color:var(--stop);background:var(--stop-bg)}
.anat-label{display:inline-block;font-family:var(--mono);font-size:.68rem;text-transform:uppercase;
  letter-spacing:.09em;font-weight:700;margin-bottom:5px;opacity:.85}
.anat-goal .anat-label{color:var(--goal)} .anat-verifier .anat-label{color:var(--verifier)}
.anat-action .anat-label{color:var(--action)}
.anat-state .anat-label{color:var(--state)} .anat-stop .anat-label{color:var(--stop)}
.anat-context .anat-label{color:var(--context)}
.anat-body{font-family:var(--mono);font-size:.86rem;line-height:1.6;color:var(--ink);white-space:normal}
.hl-verify{background:color-mix(in srgb,var(--action) 22%,transparent);border-radius:3px;padding:0 2px;font-weight:600}
.hl-invariant{background:color-mix(in srgb,var(--goal) 22%,transparent);border-radius:3px;padding:0 2px;font-weight:600}
.arm-success{color:var(--success);font-weight:700}
.arm-budget{color:var(--budget);font-weight:700}
.arm-noprogress{color:var(--noprogress);font-weight:700}
.arm-blocked{color:var(--blocked);font-weight:700}

/* detail */
.detail{padding-top:28px}
.crumbs{font-size:.85rem;color:var(--muted);margin:0 0 18px}
.detail-title{font-size:2rem;letter-spacing:-.02em;margin:0 0 10px;line-height:1.15}
.detail-alt{font-size:1rem;color:var(--muted);margin:-4px 0 10px}
.detail-when{font-size:1.1rem;color:var(--ink-soft);max-width:70ch;margin:0 0 16px}
.facets{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:26px}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:22px;flex-wrap:wrap}
.tab{background:none;border:none;border-bottom:2px solid transparent;padding:10px 14px;font-size:.95rem;
  font-weight:600;color:var(--muted);cursor:pointer;font-family:inherit}
.tab:hover{color:var(--ink)}
.tab.is-active{color:var(--accent-ink);border-bottom-color:var(--accent)}
.tabpanel{display:none}
.tabpanel.is-active{display:block;animation:fade .2s ease}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.prompt-toolbar{display:flex;align-items:center;gap:14px;margin-bottom:10px}
.copy-btn{background:var(--accent);color:#fff;border:none;border-radius:8px;padding:9px 16px;
  font-weight:600;font-size:.9rem;cursor:pointer;font-family:inherit}
.copy-btn:hover{background:var(--accent-ink)}
.copy-btn.copied{background:var(--goal)}
.prompt-meta{font-family:var(--mono);font-size:.8rem;color:var(--muted)}
.promptbody{background:var(--code-bg);color:var(--code-ink);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;font-family:var(--mono);font-size:.87rem;line-height:1.65;white-space:pre-wrap;overflow-x:auto;margin:0 0 12px}
.vars{margin-bottom:12px;font-size:.9rem}
.vars-label{font-weight:600;margin-right:6px}
.var{background:color-mix(in srgb,var(--state) 15%,var(--code-bg))}
.sub{font-size:1.15rem;margin:28px 0 12px}
.loop-steps{margin:0;padding-left:0;list-style:none;counter-reset:s}
.loop-steps li{counter-increment:s;position:relative;padding:8px 0 8px 40px;border-bottom:1px solid var(--line);font-family:var(--mono);font-size:.86rem}
.loop-steps li::before{content:counter(s);position:absolute;left:0;top:8px;width:26px;height:26px;
  background:var(--accent);color:#fff;border-radius:50%;display:grid;place-items:center;font-size:.78rem;font-weight:700}
.stoparms{display:grid;gap:8px}
.stoparm{display:grid;grid-template-columns:130px 1fr;gap:12px;padding:10px 14px;border-radius:8px;
  border:1px solid var(--line);align-items:baseline}
.stoparm .arm-name{font-family:var(--mono);font-weight:700;font-size:.82rem}
.arm-success{border-left:none}
.stoparm.arm-success{background:var(--goal-bg)} .stoparm.arm-success .arm-name{color:var(--success)}
.stoparm.arm-budget{background:var(--state-bg)} .stoparm.arm-budget .arm-name{color:var(--budget)}
.stoparm.arm-noprogress{background:color-mix(in srgb,var(--noprogress) 12%,var(--panel))} .stoparm.arm-noprogress .arm-name{color:var(--noprogress)}
.stoparm.arm-blocked{background:var(--stop-bg)} .stoparm.arm-blocked .arm-name{color:var(--blocked)}
.arm-body{font-size:.9rem;color:var(--ink-soft)}
.model-note{max-width:74ch;color:var(--ink-soft)}
.why-list{list-style:none;padding:0;display:grid;gap:12px;max-width:80ch}
.why-list li{display:flex;gap:11px;align-items:flex-start}
.why-dot{width:12px;height:12px;border-radius:3px;flex:none;margin-top:6px}
.why-dot-plain{background:var(--muted)}
.why-text{line-height:1.55}
.why-ev{color:var(--ink-soft)}
.anat-dot{display:inline-block}
.anat-dot-goal{background:var(--goal)} .anat-dot-verifier{background:var(--verifier)}
.anat-dot-action{background:var(--action)}
.anat-dot-state{background:var(--state)} .anat-dot-stop{background:var(--stop)}
.source-dl{display:grid;grid-template-columns:150px 1fr;gap:10px 18px;max-width:80ch}
.source-dl dt{font-weight:700;color:var(--ink)}
.source-dl dd{margin:0;color:var(--ink-soft)}
.dup,.dup-list{font-size:.9rem;color:var(--ink-soft)}
.dup-list{margin-top:8px}
.dup-list li{margin:5px 0}

/* library controls */
.lib{padding-top:28px}
.lib-controls{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0;align-items:center}
.search{flex:1 1 320px;min-width:240px;padding:11px 14px;border:1px solid var(--line-strong);
  border-radius:var(--radius);font-size:.95rem;font-family:inherit;background:var(--panel);color:var(--ink)}
.search:focus,.filter:focus{outline:2px solid var(--accent);outline-offset:1px}
.filter{padding:10px 12px;border:1px solid var(--line-strong);border-radius:var(--radius);
  font-size:.9rem;font-family:inherit;background:var(--panel);color:var(--ink)}
.toggle{display:flex;align-items:center;gap:7px;font-size:.9rem;color:var(--ink-soft);cursor:pointer}
.lib-count{font-family:var(--mono);font-size:.82rem;color:var(--muted);margin:0 0 16px}
.empty{color:var(--muted);padding:40px 0;text-align:center}

/* anatomy page + principles */
.anat-page{padding-top:28px}
.comp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.comp{border-left:4px solid var(--context);border-radius:8px;padding:14px 16px;background:var(--panel);border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.comp p{margin:.3em 0 0;font-size:.92rem;color:var(--ink-soft)}
.comp-goal{border-left-color:var(--goal)} .comp-verifier{border-left-color:var(--verifier)}
.comp-action{border-left-color:var(--action)}
.comp-state{border-left-color:var(--state)} .comp-stop{border-left-color:var(--stop)}
.principles{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.principle{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px}
.principle h3{margin:0 0 6px;font-size:1.02rem}
.principle p{margin:0;font-size:.92rem;color:var(--ink-soft)}
.anti{max-width:82ch;color:var(--ink-soft)}
.anti li{margin:8px 0}
.principles-teaser blockquote{margin:0 0 14px;padding:18px 22px;border-left:4px solid var(--accent);
  background:var(--panel);border-radius:8px;font-size:1.05rem;color:var(--ink);max-width:80ch}

.family{padding-top:28px}
.dup-section{margin-top:40px}

/* glossary */
.glossary{padding-top:28px}
.gsec{margin-bottom:8px}
.glist{display:grid;gap:12px;margin:0 0 8px}
.gterm{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.gterm dt{font-weight:700;color:var(--ink);margin-bottom:5px;display:flex;align-items:center;gap:9px}
.gterm dd{margin:0;color:var(--ink-soft);font-size:.94rem;line-height:1.55;max-width:82ch}
.gterm dd code{font-size:.85em}
.gloss-dot{display:inline-block;width:12px;height:12px;border-radius:3px;flex:none}

/* families index */
.fam-lg-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.fam-lg{display:flex;flex-direction:column;gap:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px}
.fam-lg:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-2px);transition:.15s}
.fam-lg-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.fam-lg .fam-name{font-weight:650;color:var(--ink);font-size:1.05rem}
.fam-desc{font-size:.9rem;color:var(--ink-soft);line-height:1.5}

/* corpus stat band (home) */
.statband-wrap{margin-top:32px}
.statband{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.stat{background:var(--panel);padding:16px 14px;text-align:center;display:flex;flex-direction:column;gap:3px}
.stat-n{font-size:1.7rem;font-weight:750;color:var(--accent-ink);letter-spacing:-.02em;line-height:1}
.stat-l{font-size:.74rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.statband-note{font-size:.88rem;color:var(--ink-soft);margin:12px 0 0}

/* pattern chips on detail */
.chip-pattern{border-color:color-mix(in srgb,var(--accent) 35%,var(--line));color:var(--accent-ink);cursor:pointer}
.chip-pattern:hover{background:color-mix(in srgb,var(--accent) 10%,var(--panel));text-decoration:none}
.patternrow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:-14px 0 26px}
.patternrow-label{font-family:var(--mono);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-right:4px}

/* complexity strip */
.cx{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin:12px 0 4px;padding:12px 14px;
  background:var(--code-bg);border-radius:8px}
.cx-band{font-family:var(--mono);font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  padding:3px 9px;border-radius:20px}
.cx-compact{background:color-mix(in srgb,var(--goal) 18%,var(--panel));color:var(--goal)}
.cx-standard{background:color-mix(in srgb,var(--action) 18%,var(--panel));color:var(--action)}
.cx-dense{background:color-mix(in srgb,var(--stop) 18%,var(--panel));color:var(--stop)}
.cx-item{font-size:.86rem;color:var(--ink-soft)}
.cx-item b{color:var(--ink);font-variant-numeric:tabular-nums}

/* related prompts */
.related{margin-top:44px;border-top:1px solid var(--line);padding-top:8px}
.rel-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.rel-card{display:flex;flex-direction:column;gap:5px;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:14px}
.rel-card:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-2px);transition:.15s}
.rel-fam{font-family:var(--mono);font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--accent-ink)}
.rel-title{font-weight:600;color:var(--ink);line-height:1.25;font-size:.95rem}
.rel-why{font-size:.8rem;color:var(--muted)}

/* pattern explorer */
.pat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.pat-card{display:flex;flex-direction:column;gap:8px;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px 18px}
.pat-card:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-2px);transition:.15s}
.pat-head{display:flex;align-items:center;gap:9px}
.pat-name{font-weight:650;color:var(--ink);flex:1}
.pat-count{font-family:var(--mono);font-weight:700;font-size:1.05rem;color:var(--accent-ink)}
.pat-desc{font-size:.88rem;color:var(--ink-soft);line-height:1.5}
.pattern-page{padding-top:28px}
.pat-blocks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:8px 0 8px}
.pat-block{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.pat-block h3{margin:0 0 6px;font-size:.95rem}
.pat-block p,.pat-block li{font-size:.9rem;color:var(--ink-soft);margin:.2em 0}
.pat-block ul{margin:0;padding-left:18px}

/* automation section */
:root{
  --step-trigger:#6a6a6a; --step-det:#2f6fd0; --step-ai:#7b4fd0; --step-val:#0f7f80;
  --step-dec:#8a6d1f; --step-human:#b0472b; --step-fallback:#b0472b; --step-notify:#8a6d1f; --step-store:#6a6a6a;
}
@media (prefers-color-scheme:dark){:root{
  --step-det:#78a9f0; --step-ai:#b48cf0; --step-val:#4fc9c8; --step-dec:#d8b45a;
  --step-human:#e8896e; --step-fallback:#e8896e; --step-notify:#d8b45a;
}}
.automation{padding-top:28px}
.step-legend{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 24px}
.step-key{display:inline-flex;align-items:center;gap:6px;font-size:.82rem;color:var(--ink-soft)}
.stepdot{width:11px;height:11px;border-radius:3px;flex:none;display:inline-block}
.step-trigger{background:var(--step-trigger)} .step-det{background:var(--step-det)}
.step-ai{background:var(--step-ai)} .step-val{background:var(--step-val)}
.step-dec{background:var(--step-dec)} .step-human{background:var(--step-human)}
.step-fallback{background:var(--step-fallback)} .step-notify{background:var(--step-notify)}
.step-store{background:var(--step-store)}
.auto-cat{margin-bottom:8px}
.auto-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.auto-card{display:flex;flex-direction:column;gap:10px;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px 18px}
.auto-card:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-2px);transition:.15s}
.auto-name{font-weight:650;color:var(--ink)}
.auto-flow{display:flex;flex-wrap:wrap;gap:5px;align-items:center}
.auto-flow .stepdot{width:14px;height:8px;border-radius:2px}
.auto-meta{font-size:.78rem;color:var(--muted);font-family:var(--mono)}
.automation-page{padding-top:28px}
.auto-facts{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 16px}
.why-ai{background:color-mix(in srgb,var(--step-ai) 10%,var(--panel));border-left:4px solid var(--step-ai);
  border-radius:8px;padding:12px 16px;max-width:80ch;color:var(--ink-soft)}
.flow{display:grid;gap:0;max-width:640px}
.flow-step{display:grid;grid-template-columns:130px 1fr;gap:12px;align-items:center;background:var(--panel);
  border:1px solid var(--line);border-radius:8px;padding:11px 14px}
.flow-badge{font-family:var(--mono);font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
  text-align:center;padding:4px 6px;border-radius:5px;color:#fff}
.flow-badge.step-trigger{background:var(--step-trigger)} .flow-badge.step-det{background:var(--step-det)}
.flow-badge.step-ai{background:var(--step-ai)} .flow-badge.step-val{background:var(--step-val)}
.flow-badge.step-dec{background:var(--step-dec);color:#1a1a1a} .flow-badge.step-human{background:var(--step-human)}
.flow-badge.step-fallback{background:var(--step-fallback)} .flow-badge.step-notify{background:var(--step-notify);color:#1a1a1a}
.flow-badge.step-store{background:var(--step-store)}
.flow-text{font-size:.92rem;color:var(--ink)}
.flow-arrow{text-align:center;color:var(--muted);font-size:1rem;line-height:1;padding:3px 0;width:130px}
.rel-list,.fail-list{max-width:80ch;color:var(--ink-soft)}
.rel-list li,.fail-list li{margin:7px 0}

/* constellation graph */
.graph-page{padding-top:28px}
.graph-controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 14px}
.graph-hint{font-size:.82rem}
.graph-stage{position:relative;border:1px solid var(--line);border-radius:var(--radius);background:var(--panel);overflow:hidden;box-shadow:var(--shadow)}
.graph-wrap{width:100%}
.graph-svg{width:100%;height:auto;display:block;max-height:74vh}
.g-edge{stroke:var(--line-strong);stroke-width:.6;opacity:.3;transition:opacity .15s,stroke .15s}
.g-edge-cur{stroke:var(--warm);opacity:.45}
.g-edge.hot{stroke:var(--accent);opacity:.9;stroke-width:1.3}
.g-edge.dim{opacity:.05}
.g-edge.off{display:none}
.g-node{cursor:pointer;stroke:var(--panel);stroke-width:1.2;transition:opacity .15s}
.g-node:hover,.g-node.hot{stroke:var(--ink)}
.g-node.dim{opacity:.2}
.g-node.off{opacity:.05;pointer-events:none}
.g-node:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.graph-panel{position:absolute;top:12px;right:12px;width:min(300px,82%);background:var(--panel);
  border:1px solid var(--line-strong);border-radius:var(--radius);padding:16px 18px;box-shadow:var(--shadow)}
.graph-panel .g-close{position:absolute;top:6px;right:10px;background:none;border:none;font-size:1.4rem;line-height:1;cursor:pointer;color:var(--muted)}
.g-fam{font-family:var(--mono);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.graph-panel h3{margin:5px 0 10px;font-size:1.05rem;line-height:1.25}
.g-pats{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.g-open{padding:9px 16px;font-size:.9rem}
.graph-fallback{margin-top:18px;color:var(--ink-soft)}
.graph-fallback>summary{cursor:pointer;font-weight:600;font-size:.9rem}
.graph-fallback details{margin:6px 0 6px 4px}
.graph-fallback summary{cursor:pointer}
@media (max-width:640px){.graph-svg{max-height:64vh}.graph-panel{position:static;width:auto;margin-top:10px;box-shadow:none}}

/* ---- warmth pass: soft cards + warm hover accents ---- */
.pcard,.fam-card,.fam-lg,.auto-card,.pat-card,.rel-card,.gterm,.principle{box-shadow:var(--shadow)}
.pcard:hover,.fam-card:hover,.fam-lg:hover,.auto-card:hover,.pat-card:hover,.rel-card:hover{border-color:var(--warm)}
.hero{background:linear-gradient(180deg,color-mix(in srgb,var(--warm) 7%,var(--bg)),var(--bg))}
.hero-divider{height:0;border:none;border-top:2px dashed var(--line-strong);opacity:.7;margin:6px 0 0}
.kicker::after{content:"";display:inline-block;width:26px;height:0;border-top:2px solid var(--warm);
  vertical-align:middle;margin-left:10px;opacity:.7}

/* ============================ MOTION SYSTEM ============================ */
/* Progressive enhancement: content is visible by default; the hidden->reveal
   state applies ONLY under .motion-ok (set by JS when reduced-motion is off). */
.motion-ok .reveal{opacity:0;transform:translateY(var(--move-2));
  transition:opacity var(--dur-standard) var(--ease-entrance), transform var(--dur-standard) var(--ease-entrance)}
.motion-ok .reveal.in{opacity:1;transform:none}

/* hero animation */
.hero-anim{margin-top:30px;display:grid;gap:18px;max-width:560px}
.hero-typed{font-family:var(--mono);font-size:.92rem;color:var(--ink-soft);min-height:1.5em;
  border-left:3px solid var(--accent);padding:6px 0 6px 12px}
.hero-typed .caret{display:none}
.motion-ok .hero-typed .caret{display:inline-block;width:2px;height:1em;background:var(--accent);
  vertical-align:-2px;margin-left:1px;animation:blink 1s step-end infinite}
@keyframes blink{50%{opacity:0}}
.hero-chips{display:flex;flex-wrap:wrap;gap:8px}
.hero-chip{font-family:var(--mono);font-size:.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  padding:5px 11px;border-radius:20px;border:1px solid;background:var(--panel)}
.hero-chip.c-goal{color:var(--goal);border-color:var(--goal)}
.hero-chip.c-context{color:var(--context);border-color:var(--line-strong)}
.hero-chip.c-process{color:var(--action);border-color:var(--action)}
.hero-chip.c-verifier{color:var(--verifier);border-color:var(--verifier)}
.hero-chip.c-stop{color:var(--stop);border-color:var(--stop)}
.motion-ok .hero-chip{opacity:0;transform:translateY(8px) scale(.96);
  transition:opacity var(--dur-fast) var(--ease-spring), transform var(--dur-fast) var(--ease-spring)}
.motion-ok .hero-anim.s2 .hero-chip,.motion-ok .hero-anim.s3 .hero-chip{opacity:1;transform:none;transition-delay:calc(var(--i,0)*80ms)}
.hero-ring{width:200px;height:200px}
.hero-ring-path{fill:none;stroke:var(--accent);stroke-width:2;opacity:.55}
.motion-ok .hero-ring-path{stroke-dasharray:var(--len);stroke-dashoffset:var(--len)}
.motion-ok .hero-anim.s3 .hero-ring-path{stroke-dashoffset:0;transition:stroke-dashoffset var(--dur-cine) var(--ease-entrance)}
.hero-node circle{fill:var(--panel);stroke:var(--accent);stroke-width:2}
.hero-node text{font-family:var(--mono);font-size:8px;fill:var(--ink-soft)}
.motion-ok .hero-node{opacity:0} .motion-ok .hero-anim.s3 .hero-node{opacity:1;transition:opacity var(--dur-standard) var(--ease-entrance);transition-delay:calc(var(--i,0)*120ms + 400ms)}
.hero-pulse{fill:var(--accent)}
.motion-ok .hero-anim.s3 .hero-spin{animation:spin 14s linear infinite;transform-origin:100px 100px}
.tab-hidden .hero-spin,.tab-hidden .runner-dot{animation-play-state:paused!important}
@keyframes spin{to{transform:rotate(360deg)}}
.hero-cap{font-family:var(--mono);font-size:.74rem;color:var(--muted)}
.hero-replay{background:none;border:1px solid var(--line-strong);color:var(--ink-soft);border-radius:20px;
  padding:5px 13px;font-size:.78rem;cursor:pointer;font-family:inherit;justify-self:start}
.hero-replay:hover{border-color:var(--accent);color:var(--accent-ink)}
.hero-replay[hidden]{display:none}

/* counters */
.stat-n[data-target]{font-variant-numeric:tabular-nums}

/* loop visualizer */
.loopviz{margin-top:8px}
.lv-stage{display:grid;grid-template-columns:230px 1fr;gap:22px;align-items:start;
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:20px}
.lv-ring{width:230px;height:230px}
.lv-ring-path{fill:none;stroke:var(--line-strong);stroke-width:2}
.lv-node circle{fill:var(--panel);stroke:var(--line-strong);stroke-width:2;transition:all var(--dur-standard) var(--ease-spring)}
.lv-node text{font-family:var(--mono);font-size:8.5px;fill:var(--muted);transition:fill var(--dur-standard)}
.lv-node.active circle{fill:var(--accent);stroke:var(--accent);r:11}
.lv-node.active text{fill:var(--ink);font-weight:700}
.lv-node.done circle{stroke:var(--goal)}
.lv-panel{min-height:200px}
.lv-step-label{font-family:var(--mono);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--accent-ink);font-weight:700}
.lv-step-title{font-size:1.15rem;font-weight:650;margin:4px 0 8px}
.lv-step-desc{color:var(--ink-soft);font-size:.94rem;line-height:1.55;min-height:3em}
.lv-quote{font-family:var(--mono);font-size:.82rem;background:var(--code-bg);border-radius:8px;padding:10px 12px;margin-top:12px;color:var(--code-ink)}
.lv-controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:16px 0}
.lv-btn{background:var(--panel);border:1px solid var(--line-strong);border-radius:8px;padding:8px 14px;
  font-size:.88rem;font-weight:600;cursor:pointer;font-family:inherit;color:var(--ink)}
.lv-btn:hover{border-color:var(--accent);color:var(--accent-ink)}
.lv-btn.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.lv-btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.lv-presets{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.lv-preset{font-size:.82rem;padding:6px 12px;border-radius:20px;border:1px solid var(--line-strong);
  background:var(--panel);cursor:pointer;color:var(--ink-soft);font-family:inherit}
.lv-preset.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.lv-exits{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
.lv-exit{font-family:var(--mono);font-size:.72rem;font-weight:700;padding:4px 10px;border-radius:6px;cursor:pointer;border:1px solid}
.lv-exit.x-success{color:var(--success);border-color:var(--success)} .lv-exit.x-budget{color:var(--budget);border-color:var(--budget)}
.lv-exit.x-noprogress{color:var(--noprogress);border-color:var(--noprogress)} .lv-exit.x-blocked{color:var(--blocked);border-color:var(--blocked)}
.lv-exit.fired{color:#fff} .lv-exit.x-success.fired{background:var(--success)} .lv-exit.x-budget.fired{background:var(--budget)}
.lv-exit.x-noprogress.fired{background:var(--noprogress)} .lv-exit.x-blocked.fired{background:var(--blocked)}
.loopviz-page{padding-top:28px}
.loopviz:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:var(--radius)}
.lv-fallback{margin-top:20px;color:var(--ink-soft);font-size:.9rem;max-width:80ch}
.lv-fallback li{margin:6px 0}

/* automation run simulation */
.auto-run{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0}
.auto-run select{padding:8px 10px;border:1px solid var(--line-strong);border-radius:8px;font-family:inherit;background:var(--panel);color:var(--ink)}
.flow-step{transition:border-color var(--dur-standard),background var(--dur-standard),transform var(--dur-fast) var(--ease-spring)}
.flow-step.active{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,var(--panel));transform:translateX(4px)}
.flow-step.done{border-color:var(--goal)}
.flow-step.skipped{opacity:.4}
.flow-step.failed{border-color:var(--stop);background:color-mix(in srgb,var(--stop) 8%,var(--panel))}
.run-status{font-family:var(--mono);font-size:.82rem;padding:8px 12px;border-radius:8px;background:var(--code-bg);margin-top:6px;min-height:1.2em}

/* reduced-motion: hard stop, snap to final states */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:1ms!important;animation-iteration-count:1!important;
    transition-duration:1ms!important;scroll-behavior:auto!important}
  .reveal{opacity:1!important;transform:none!important}
  .hero-spin{animation:none!important}
}

@media (max-width:820px){.statband{grid-template-columns:repeat(2,1fr)}
  .lv-stage{grid-template-columns:1fr}.lv-ring{width:200px;height:200px;margin:0 auto}}
@media (max-width:640px){
  .flow-step{grid-template-columns:1fr;gap:4px}
  .flow-arrow{width:100%}
  .source-dl{grid-template-columns:1fr;gap:2px 0}
  .source-dl dd{margin-bottom:10px}
  .stoparm{grid-template-columns:1fr;gap:2px}
  .hero{padding:48px 0 32px}
  .site-head nav{gap:15px}
  .site-head nav a{font-size:.9rem}
}
@media (max-width:460px){
  .head-inner{height:auto;min-height:56px;flex-wrap:wrap;padding:8px 0;gap:2px 14px}
  .brand{flex:1 1 100%}
  .site-head nav{gap:14px;flex-wrap:wrap}
  .statband{grid-template-columns:repeat(2,1fr)}
  .stat-n{font-size:1.45rem}
}
"""

JS = r"""'use strict';
// Tabs (detail page)
document.querySelectorAll('.tabs').forEach(function (tabs) {
  var panels = tabs.parentElement;
  tabs.addEventListener('click', function (e) {
    var btn = e.target.closest('.tab');
    if (!btn) return;
    tabs.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('is-active'); });
    btn.classList.add('is-active');
    var name = btn.getAttribute('data-tab');
    panels.querySelectorAll('.tabpanel').forEach(function (p) {
      var on = p.getAttribute('data-panel') === name;
      p.classList.toggle('is-active', on);
      // Reveal a panel's blocks when its tab opens — IntersectionObserver is unreliable
      // for elements that were inside a display:none panel, so trigger it explicitly here.
      if (on) {
        var revs = p.querySelectorAll('.reveal');
        for (var i = 0; i < revs.length; i++) {
          (function (el, idx) { setTimeout(function () { el.classList.add('in'); }, Math.min(idx, 6) * 70); })(revs[i], i);
        }
      }
    });
  });
});

// Copy buttons
document.querySelectorAll('.copy-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var el = document.getElementById(btn.getAttribute('data-copy-target'));
    if (!el) return;
    var text = el.innerText;
    var done = function () {
      var old = btn.textContent;
      btn.textContent = 'Copied ✓'; btn.classList.add('copied');
      setTimeout(function () { btn.textContent = old; btn.classList.remove('copied'); }, 1600);
    };
    if (navigator.clipboard) { navigator.clipboard.writeText(text).then(done, done); }
    else {
      var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
      ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove(); done();
    }
  });
});

// Library search + filters
var results = document.getElementById('results');
if (results) {
  var state = { q: '', family: '', verifier: '', model: '', starter: false, data: [] };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  function chip(t, c) { return '<span class="chip ' + (c || '') + '">' + esc(t) + '</span>'; }
  function facets(p) {
    var out = [chip(p.family_title, 'chip-family')];
    if (p.starter) out.push(chip('starter', 'chip-starter'));
    if (p.verifier_type === 'mechanical' || p.verifier_type === 'judge' || p.verifier_type === 'mixed')
      out.push(chip(p.verifier_type + ' verifier', 'chip-verifier chip-' + p.verifier_type));
    out.push(chip(p.model_hint + ' model', 'chip-model'));
    return out.join('');
  }
  function card(p) {
    var alt = p.alt ? '<span class="pcard-alt">' + esc(p.alt) + '</span>' : '';
    return '<a class="pcard" href="prompt/' + p.id + '.html">' +
      '<span class="pcard-fam">' + esc(p.family_title) + '</span>' +
      '<span class="pcard-title">' + esc(p.title) + '</span>' + alt +
      '<span class="pcard-when">' + esc((p.when || '').slice(0, 120)) + '…</span>' +
      '<span class="pcard-foot">' + facets(p) + '</span></a>';
  }
  function match(p) {
    if (state.family && p.family_key !== state.family) return false;
    if (state.verifier && p.verifier_type !== state.verifier) return false;
    if (state.model && p.model_hint !== state.model) return false;
    if (state.starter && !p.starter) return false;
    if (state.q) {
      var hay = (p.title + ' ' + (p.alt || '') + ' ' + (p.full_title || '') + ' ' +
                 p.when + ' ' + p.family_title + ' ' + p.prompt_text).toLowerCase();
      if (hay.indexOf(state.q) === -1) return false;
    }
    return true;
  }
  function render() {
    var list = state.data.filter(match);
    results.innerHTML = list.map(card).join('');
    document.getElementById('count').textContent =
      list.length + ' of ' + state.data.length + ' prompts';
    document.getElementById('empty').hidden = list.length !== 0;
  }
  var bind = function (id, key, ev) {
    var el = document.getElementById(id); if (!el) return;
    el.addEventListener(ev || 'input', function () {
      state[key] = el.type === 'checkbox' ? el.checked
        : (key === 'q' ? el.value.toLowerCase().trim() : el.value);
      render();
    });
  };
  fetch('data/prompts.json').then(function (r) { return r.json(); }).then(function (d) {
    state.data = d;
    bind('q', 'q'); bind('f-family', 'family', 'change');
    bind('f-verifier', 'verifier', 'change'); bind('f-model', 'model', 'change');
    bind('f-starter', 'starter', 'change');
    render();
  });
}

/* ============================ MOTION SYSTEM ============================ */
(function () {
  'use strict';
  var motionOK = document.documentElement.classList.contains('motion-ok');
  var hasIO = 'IntersectionObserver' in window;
  document.addEventListener('visibilitychange', function () {
    document.documentElement.classList.toggle('tab-hidden', document.hidden);
  });

  // reveal-on-scroll, once
  (function () {
    var els = [].slice.call(document.querySelectorAll('.reveal'));
    if (!els.length) return;
    if (!motionOK || !hasIO) { els.forEach(function (e) { e.classList.add('in'); }); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, par = el.parentElement;
        var sibs = par ? [].slice.call(par.children).filter(function (c) { return c.classList.contains('reveal'); }) : [el];
        el.style.transitionDelay = Math.min(sibs.indexOf(el), 6) * 60 + 'ms';
        el.classList.add('in'); io.unobserve(el);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (e) { io.observe(e); });
  })();

  // counters: 0 -> real value, once, on view
  (function () {
    var els = [].slice.call(document.querySelectorAll('[data-target]'));
    if (!els.length) return;
    function run(el) {
      var target = parseFloat(el.getAttribute('data-target'));
      var dec = el.getAttribute('data-dec') === '1';
      var fin = function () { el.textContent = dec ? target.toFixed(1) : String(target); };
      // Real value is already in the HTML. Only animate when motion is on AND the tab is
      // visible; otherwise leave the true value (never show a stuck fabricated zero).
      if (!motionOK || document.hidden) { fin(); return; }
      el.textContent = dec ? '0.0' : '0';
      var start = null, dur = 1100;
      function tick(ts) {
        if (document.hidden) { fin(); return; }
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur), e = 1 - Math.pow(1 - p, 3), v = target * e;
        el.textContent = dec ? v.toFixed(1) : String(Math.round(v));
        if (p < 1) requestAnimationFrame(tick); else fin();
      }
      requestAnimationFrame(tick);
    }
    if (!hasIO) { els.forEach(run); return; }
    var io = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { run(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.5 });
    els.forEach(function (e) { io.observe(e); });
  })();

  // hero sequence
  (function () {
    var anim = document.getElementById('heroAnim'); if (!anim) return;
    var typed = anim.querySelector('.hero-typed'), full = typed ? (typed.getAttribute('data-text') || '') : '';
    var replay = anim.querySelector('.hero-replay'), timers = [];
    function clear() { timers.forEach(clearTimeout); timers = []; }
    function stat() { if (typed) typed.textContent = full; anim.classList.add('s2', 's3'); if (replay) replay.hidden = false; }
    function play() {
      clear(); anim.classList.remove('s2', 's3'); if (replay) replay.hidden = true;
      var i = 0;
      function type() {
        if (document.hidden) { timers.push(setTimeout(type, 140)); return; }
        i++; if (typed) typed.innerHTML = escapeHtml(full.slice(0, i)) + '<span class="caret"></span>';
        if (i < full.length) { timers.push(setTimeout(type, 20)); return; }
        if (typed) typed.innerHTML = escapeHtml(full) + '<span class="caret"></span>';
        timers.push(setTimeout(function () { anim.classList.add('s2'); }, 250));
        timers.push(setTimeout(function () { anim.classList.add('s3'); if (replay) replay.hidden = false; }, 950));
      }
      type();
    }
    function escapeHtml(s) { return s.replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
    if (!motionOK) { stat(); return; }
    if (replay) replay.addEventListener('click', play);
    if (hasIO) {
      var io = new IntersectionObserver(function (ents) {
        ents.forEach(function (en) { if (en.isIntersecting) { play(); io.unobserve(en.target); } });
      }, { threshold: 0.3 });
      io.observe(anim);
    } else play();
  })();

  // loop visualizer
  (function () {
    var root = document.getElementById('loopviz'); if (!root || !window.LOOPVIZ) return;
    var presets = window.LOOPVIZ, keys = Object.keys(presets);
    var ringWrap = root.querySelector('.lv-ring-wrap'), panel = root.querySelector('.lv-panel');
    var presetBar = root.querySelector('.lv-presets'), exitBar = root.querySelector('.lv-exits');
    var cur = keys[0], step = 0, playing = false, timer = null, speed = 1;
    var SVGNS = 'http://www.w3.org/2000/svg';

    function buildRing(steps) {
      var n = steps.length, cx = 115, cy = 115, r = 82;
      var svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('viewBox', '0 0 230 230'); svg.setAttribute('class', 'lv-ring');
      svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'Loop with ' + n + ' steps');
      var circ = document.createElementNS(SVGNS, 'circle');
      circ.setAttribute('cx', cx); circ.setAttribute('cy', cy); circ.setAttribute('r', r); circ.setAttribute('class', 'lv-ring-path');
      svg.appendChild(circ);
      steps.forEach(function (s, i) {
        var a = -Math.PI / 2 + i * 2 * Math.PI / n, x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
        var g = document.createElementNS(SVGNS, 'g'); g.setAttribute('class', 'lv-node'); g.setAttribute('data-i', i);
        var c = document.createElementNS(SVGNS, 'circle'); c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('r', 8);
        var t = document.createElementNS(SVGNS, 'text'); t.setAttribute('x', x); t.setAttribute('y', y - 13);
        t.setAttribute('text-anchor', 'middle'); t.textContent = s.label;
        g.appendChild(c); g.appendChild(t);
        g.addEventListener('click', function () { pause(); step = i; render(); });
        svg.appendChild(g);
      });
      ringWrap.innerHTML = ''; ringWrap.appendChild(svg);
    }
    function render() {
      var d = presets[cur], s = d.steps[step];
      [].slice.call(ringWrap.querySelectorAll('.lv-node')).forEach(function (g, i) {
        g.classList.toggle('active', i === step); g.classList.toggle('done', i < step);
      });
      panel.querySelector('.lv-step-label').textContent = 'Step ' + (step + 1) + ' / ' + d.steps.length;
      panel.querySelector('.lv-step-title').textContent = s.label;
      panel.querySelector('.lv-step-desc').textContent = s.desc;
      var q = panel.querySelector('.lv-quote'); q.hidden = !s.quote; if (s.quote) q.textContent = s.quote;
    }
    function next() { var d = presets[cur]; step = (step + 1) % d.steps.length; render(); }
    function prev() { var d = presets[cur]; step = (step - 1 + d.steps.length) % d.steps.length; render(); }
    function tick() { if (!playing) return; if (!document.hidden) next(); timer = setTimeout(tick, 1600 / speed); }
    function playPause() {
      playing = !playing; root.querySelector('.lv-play').textContent = playing ? '⏸ Pause' : '▶ Play';
      if (playing && motionOK) { clearTimeout(timer); tick(); } else clearTimeout(timer);
    }
    function pause() { playing = false; root.querySelector('.lv-play').textContent = '▶ Play'; clearTimeout(timer); }
    function loadPreset(k) {
      cur = k; step = 0; pause();
      [].slice.call(presetBar.children).forEach(function (b) { b.classList.toggle('active', b.getAttribute('data-k') === k); });
      buildRing(presets[k].steps);
      var ex = presets[k].exits || {};
      exitBar.innerHTML = Object.keys(ex).map(function (name) {
        var cls = 'x-' + name.toLowerCase().replace('_', '');
        return '<button class="lv-exit ' + cls + '" data-exit="' + name + '">' + name + '</button>';
      }).join('');
      [].slice.call(exitBar.children).forEach(function (b) {
        b.addEventListener('click', function () {
          pause();
          [].slice.call(exitBar.children).forEach(function (x) { x.classList.remove('fired'); });
          b.classList.add('fired');
          panel.querySelector('.lv-step-title').textContent = 'Exit: ' + b.getAttribute('data-exit');
          panel.querySelector('.lv-step-desc').textContent = ex[b.getAttribute('data-exit')];
          panel.querySelector('.lv-quote').hidden = true;
        });
      });
      render();
    }
    [].slice.call(presetBar.children).forEach(function (b) {
      b.addEventListener('click', function () { loadPreset(b.getAttribute('data-k')); });
    });
    root.querySelector('.lv-play').addEventListener('click', playPause);
    root.querySelector('.lv-next').addEventListener('click', function () { pause(); next(); });
    root.querySelector('.lv-prev').addEventListener('click', function () { pause(); prev(); });
    root.querySelector('.lv-restart').addEventListener('click', function () { pause(); step = 0; render(); });
    var spd = root.querySelector('.lv-speed');
    if (spd) spd.addEventListener('click', function () { speed = speed >= 2 ? 0.5 : speed + 0.5; spd.textContent = speed + '×'; if (playing) { clearTimeout(timer); tick(); } });
    root.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { pause(); next(); } else if (e.key === 'ArrowLeft') { pause(); prev(); }
      else if (e.key === ' ') { e.preventDefault(); playPause(); }
    });
    loadPreset(cur);
    var fb = root.querySelector('.lv-fallback'); if (fb) fb.hidden = true;
  })();

  // automation run simulation
  (function () {
    var flow = document.querySelector('.flow[data-run]'); if (!flow) return;
    var steps = [].slice.call(flow.querySelectorAll('.flow-step'));
    var runBtn = document.getElementById('autoRun'), sel = document.getElementById('autoCond');
    var status = document.getElementById('autoStatus'); if (!runBtn) return;
    var timers = [];
    function typeOf(el) { var b = el.querySelector('.flow-badge'); return b ? b.textContent.trim() : ''; }
    function clearRun() {
      timers.forEach(clearTimeout); timers = [];
      steps.forEach(function (s) { s.classList.remove('active', 'done', 'skipped', 'failed'); });
      if (status) status.textContent = '';
    }
    function findType(t) { for (var i = 0; i < steps.length; i++) if (typeOf(steps[i]) === t) return i; return -1; }
    function run() {
      clearRun();
      var cond = sel ? sel.value : 'success';
      var stopAt = steps.length, note = 'Completed successfully.';
      var fallbackIdx = findType('Fallback'), decIdx = findType('Decision gate'), valIdx = findType('Validation'),
        humanIdx = findType('Human approval'), detIdx = -1;
      steps.forEach(function (s, i) { if (typeOf(s) === 'Deterministic' && detIdx < 0) detIdx = i; });
      var branchTo = -1;
      if (cond === 'low-confidence' && (decIdx >= 0 || valIdx >= 0)) { stopAt = (decIdx >= 0 ? decIdx : valIdx) + 1; branchTo = fallbackIdx; note = 'Low confidence → routed to human review (fallback).'; }
      else if (cond === 'invalid-output' && valIdx >= 0) { stopAt = valIdx + 1; branchTo = fallbackIdx; note = 'AI output failed validation → fallback / retry.'; }
      else if (cond === 'human-reject' && humanIdx >= 0) { stopAt = humanIdx + 1; note = 'Human rejected the draft — nothing was sent.'; }
      else if (cond === 'api-timeout' && detIdx >= 0) { note = 'Deterministic step timed out → retried with backoff, then continued.'; }
      var i = 0, delay = motionOK ? 480 : 0;
      function walk() {
        if (i >= stopAt) {
          if (branchTo >= 0) { steps[branchTo].classList.remove('skipped'); steps[branchTo].classList.add('active');
            for (var k = 0; k < steps.length; k++) if (k >= stopAt && k !== branchTo) steps[k].classList.add('skipped'); }
          if (status) status.textContent = note; return;
        }
        var s = steps[i];
        if (cond === 'api-timeout' && i === detIdx) {
          s.classList.add('failed');
          timers.push(setTimeout(function () { s.classList.remove('failed'); s.classList.add('done'); i++; timers.push(setTimeout(walk, delay)); }, delay * 1.4));
          if (status) status.textContent = 'Timeout at deterministic step — retrying…';
          return;
        }
        s.classList.add('active');
        timers.push(setTimeout(function () { s.classList.remove('active'); s.classList.add('done'); i++; walk(); }, delay));
      }
      if (!motionOK) { for (var j = 0; j < stopAt; j++) steps[j].classList.add('done'); if (branchTo >= 0) steps[branchTo].classList.add('active'); if (status) status.textContent = note; return; }
      walk();
    }
    runBtn.addEventListener('click', run);
  })();
})();

/* ===================== CONSTELLATION GRAPH ===================== */
(function () {
  'use strict';
  var wrap = document.getElementById('graphWrap');
  if (!wrap || !window.GRAPH) return;
  var G = window.GRAPH, N = G.nodes, E = G.edges, F = G.families.length;
  var SVGNS = 'http://www.w3.org/2000/svg';
  var W = 1000, H = 720, cx = 500, cy = 360, R = 260;
  var within = {};
  N.forEach(function (n) {
    var a = -Math.PI / 2 + n.f * 2 * Math.PI / F;
    var fx = cx + R * Math.cos(a), fy = cy + R * Math.sin(a);
    var k = (within[n.f] = (within[n.f] || 0)); within[n.f]++;
    var rr = 10 * Math.sqrt(k + 1), aa = (k + 1) * 2.399963;
    n.x = fx + rr * Math.cos(aa); n.y = fy + rr * Math.sin(aa);
    n.hue = Math.round(n.f / F * 360);
  });
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('class', 'graph-svg');
  var gE = document.createElementNS(SVGNS, 'g');
  var edgeEls = E.map(function (e) {
    var l = document.createElementNS(SVGNS, 'line');
    l.setAttribute('x1', N[e.s].x.toFixed(1)); l.setAttribute('y1', N[e.s].y.toFixed(1));
    l.setAttribute('x2', N[e.t].x.toFixed(1)); l.setAttribute('y2', N[e.t].y.toFixed(1));
    l.setAttribute('class', e.c ? 'g-edge g-edge-cur' : 'g-edge'); gE.appendChild(l); return l;
  });
  svg.appendChild(gE);
  var adj = N.map(function () { return []; });
  E.forEach(function (e) { adj[e.s].push(e.t); adj[e.t].push(e.s); });
  var gN = document.createElementNS(SVGNS, 'g');
  var nodeEls = N.map(function (n, i) {
    var c = document.createElementNS(SVGNS, 'circle');
    c.setAttribute('cx', n.x.toFixed(1)); c.setAttribute('cy', n.y.toFixed(1)); c.setAttribute('r', 5);
    c.setAttribute('fill', 'hsl(' + n.hue + ',58%,52%)'); c.setAttribute('class', 'g-node');
    c.setAttribute('tabindex', '0'); c.setAttribute('role', 'button');
    c.setAttribute('aria-label', n.t + ' — ' + (G.families[n.f] ? G.families[n.f].title : ''));
    gN.appendChild(c); return c;
  });
  svg.appendChild(gN); wrap.appendChild(svg);
  var panel = document.getElementById('graphPanel');
  function hi(i) {
    var near = {}; near[i] = 1; adj[i].forEach(function (j) { near[j] = 1; });
    nodeEls.forEach(function (el, j) { el.classList.toggle('dim', !near[j]); el.classList.toggle('hot', j === i); });
    edgeEls.forEach(function (el, j) { var on = E[j].s === i || E[j].t === i; el.classList.toggle('hot', on); el.classList.toggle('dim', !on); });
  }
  function clr() { nodeEls.forEach(function (el) { el.classList.remove('dim', 'hot'); }); edgeEls.forEach(function (el) { el.classList.remove('dim', 'hot'); }); }
  function open(i) {
    var n = N[i]; panel.hidden = false;
    panel.innerHTML = '<button class="g-close" aria-label="Close">×</button>' +
      '<span class="g-fam" style="color:hsl(' + n.hue + ',58%,44%)">' + esc(G.families[n.f].title) + '</span>' +
      '<h3>' + esc(n.t) + '</h3>' +
      (n.p.length ? '<div class="g-pats">' + n.p.map(function (p) { return '<span class="chip">' + esc(p) + '</span>'; }).join('') + '</div>' : '') +
      '<a class="btn btn-primary g-open" href="prompt/' + n.id + '.html">Open prompt →</a>';
    panel.querySelector('.g-close').addEventListener('click', function () { panel.hidden = true; });
  }
  nodeEls.forEach(function (el, i) {
    el.addEventListener('mouseenter', function () { hi(i); });
    el.addEventListener('mouseleave', clr);
    el.addEventListener('focus', function () { hi(i); });
    el.addEventListener('click', function () { hi(i); open(i); });
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hi(i); open(i); } });
  });
  var fsel = document.getElementById('g-family');
  if (fsel) fsel.addEventListener('change', function () {
    var k = fsel.value;
    nodeEls.forEach(function (el, j) { el.classList.toggle('off', !!k && N[j].fk !== k); });
    edgeEls.forEach(function (el, j) { el.classList.toggle('off', !!k && N[E[j].s].fk !== k && N[E[j].t].fk !== k); });
  });
  var rb = document.getElementById('g-reset');
  if (rb) rb.addEventListener('click', function () { clr(); if (panel) panel.hidden = true; if (fsel) { fsel.value = ''; fsel.dispatchEvent(new Event('change')); } });
})();
"""


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

def build():
    global ASSET_VER
    ASSET_VER = hashlib.md5((CSS + JS).encode("utf-8")).hexdigest()[:8]

    prompts: list[dict] = []
    for key, _ in FAMILIES:
        prompts.extend(parse_family(key))

    # mark starter-set membership: exact match, or the starter's English title nested
    # inside a '中文(English)' prompt title (e.g. 'Fan-Out Research Synthesis').
    starter_titles = [t.lower() for t in parse_starter_titles()]
    for p in prompts:
        tl = p["title"].lower()
        if any(st == tl or st in tl for st in starter_titles):
            p["starter"] = True

    principles = parse_principles()

    # sanity: every declared family must contribute prompts (count grows as the corpus does)
    n = len(prompts)
    empty_fams = [k for k, _ in FAMILIES if not any(p["family_key"] == k for p in prompts)]
    if empty_fams:
        print(f"  ! WARNING: families with no parsed prompts: {empty_fams}")
    missing = [p["id"] for p in prompts if not p["prompt_text"]]
    if missing:
        print(f"  ! WARNING: {len(missing)} prompts have empty prompt_text: {missing[:5]}")
    starters = sum(1 for p in prompts if p["starter"])

    # analysis (deterministic)
    stats = corpus_stats(prompts)
    stats["generated_pages"] = 9 + len(prompts) + len(FAMILIES) + len(PATTERN_META) + len(AUTOMATIONS)
    related = build_related(prompts)
    # optional authored pattern reference docs (produced by the pattern workflow); seed
    # blurbs are used when absent, so the site is complete with or without them.
    docs_path = ROOT / "pattern_docs.json"
    pat_docs = json.loads(docs_path.read_text(encoding="utf-8")) if docs_path.exists() else {}
    auto_path = ROOT / "automation_docs.json"
    auto_docs = json.loads(auto_path.read_text(encoding="utf-8")) if auto_path.exists() else {}

    # clean output
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "prompt").mkdir(parents=True)
    (SITE / "family").mkdir(parents=True)
    (SITE / "pattern").mkdir(parents=True)
    (SITE / "automation").mkdir(parents=True)
    (SITE / "data").mkdir(parents=True)
    (SITE / "assets").mkdir(parents=True)

    (SITE / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (SITE / "assets" / "app.js").write_text(JS, encoding="utf-8")

    # JSON search index (trim prompt_text to keep it lean but searchable)
    index = [{
        "id": p["id"], "title": p["display_title"], "alt": p["alt_title"],
        "full_title": p["title"], "when": p["when"],
        "family_key": p["family_key"], "family_title": p["family_title"],
        "verifier_type": p["verifier_type"], "model_hint": p["model_hint"],
        "length_bucket": p["length_bucket"], "starter": p["starter"],
        "prompt_text": p["prompt_text"],
    } for p in prompts]
    (SITE / "data" / "prompts.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    (SITE / "index.html").write_text(render_home(prompts, principles, stats), encoding="utf-8")
    (SITE / "library.html").write_text(render_library(), encoding="utf-8")
    (SITE / "anatomy.html").write_text(render_anatomy_page(principles, prompts), encoding="utf-8")
    (SITE / "families.html").write_text(render_families_index(prompts), encoding="utf-8")
    (SITE / "glossary.html").write_text(render_glossary(), encoding="utf-8")
    (SITE / "patterns.html").write_text(render_patterns_index(stats, pat_docs), encoding="utf-8")
    (SITE / "graph.html").write_text(render_graph(prompts, related), encoding="utf-8")
    (SITE / "loops.html").write_text(render_loops(prompts), encoding="utf-8")
    (SITE / "automation.html").write_text(render_automation_index(), encoding="utf-8")
    for a in AUTOMATIONS:
        (SITE / "automation" / f"{a['key']}.html").write_text(
            render_automation_page(a, auto_docs.get(a["key"], {})), encoding="utf-8")

    for p in prompts:
        (SITE / "prompt" / f"{p['id']}.html").write_text(render_detail(p, related[p["id"]]), encoding="utf-8")
    for key, title in FAMILIES:
        (SITE / "family" / f"{key}.html").write_text(render_family(key, title, prompts), encoding="utf-8")
    for key, name, role, blurb in PATTERN_META:
        (SITE / "pattern" / f"{key}.html").write_text(
            render_pattern_page(key, name, role, blurb, prompts, pat_docs.get(key, {})), encoding="utf-8")

    total_pages = 9 + len(prompts) + len(FAMILIES) + len(PATTERN_META) + len(AUTOMATIONS)  # +patterns,+automation,+loops,+graph
    print(f"  parsed {n} prompts across {len(FAMILIES)} families ({starters} in starter set)")
    print(f"  wrote {total_pages} HTML pages + prompts.json + style.css + app.js -> {SITE.relative_to(ROOT)}/")
    print(f"  open: {SITE / 'index.html'}")


if __name__ == "__main__":
    build()
