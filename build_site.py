#!/usr/bin/env python3
"""Build the prompt-os educational website from the loop-prompt library.

Source of truth: loops/*.md + loops/00-loop-engineering-principles.md.
Output: site/ — a static, dependency-free educational site:

    site/index.html              Home
    site/library.html            Searchable/filterable library of all parsed prompts (client-side)
    site/anatomy.html            The universal loop anatomy + principles
    site/prompt/<id>.html        Prompt detail pages (Prompt / Anatomy / Why it works / Source)
    site/family/<key>.html       Family pages (with curation/redundancy notes)
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
import base64
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
LOOPS = ROOT / "loops"
SITE = ROOT / "site"
import os
# Canonical/OG/sitemap origin. Defaults to localhost so a fork or an unconfigured
# build cannot silently emit canonical URLs pointing at someone else's deployment.
BASE_URL = os.environ.get("PROMPT_OS_BASE_URL", "http://localhost:8199/")
if not BASE_URL.endswith("/"):
    BASE_URL += "/"
ASSET_VER = "0"  # content hash of CSS+JS, set in build() for cache-busting
CORPUS_PROMPT_COUNT = 0  # set in build(); used by shared page chrome

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
    "agent-memory": "Maintain, consolidate, and verify durable agent memory without losing facts, duplicating entries, or accepting unverified writes.",
    "api-integration": "Implement and harden API integrations against fixed contracts, sandbox checks, idempotency, rate limits, and rollback-safe error handling.",
    "data-labeling": "Label data against a frozen taxonomy with independent agreement checks, adjudication, and drift or quality gates.",
    "incident-response": "Drive incident response from triage to verified mitigation with one action per turn, evidence capture, and explicit escalation gates.",
    "structured-extraction": "Extract structured records from messy documents with schema validation, independent corroboration, and human-review fallback when fields cannot be trusted.",
    "video-generation": "Iterate video generations against frozen visual, OCR, or motion verifiers, with cost gates and human approval before paid or public steps.",
    "translation-localization": "Translate and localize verified by an independent signal — blind back-translation or a mechanical placeholder/length/glossary linter — not the translator's own read.",
    "performance-optimization": "Speed and memory loops where every change is kept only if a frozen benchmark or profiler measures the win, with correctness held green — never an unmeasured 'should be faster'.",
    "accessibility-audit": "Drive a UI toward accessibility one fix per turn, verified by an automated scanner or scripted keyboard/AT harness, honest that passing automation is a floor, not proof.",
    "security-pentest": "Authorized, defensive security testing where a finding counts only if a proof-of-concept reproduces, and a fix counts only if the PoC stops reproducing plus a regression test bites.",
    "summarization-faithful": "Summarize or synthesize so every claim traces to a source span an independent checker confirms — remove what can't be supported, surface contradictions instead of averaging them.",
    "jailbreak-hardening": "Harden guardrails against jailbreaks and prompt-injection against a frozen red-team suite, keeping a held-out set, gated on blocking attacks AND preserving benign/legitimate behavior.",
    "dependency-upgrade": "Bump dependencies (major-version or security patch) one at a time, verified by build + typecheck + tests going green and an independent re-scan, never by weakening a test.",
    "flaky-test-stabilization": "Make an intermittent test deterministic by fixing the one source of nondeterminism, verified by repeated runs staying green while still catching the real bug.",
    "config-drift": "Reconcile live infrastructure/config back to the declared IaC and policy, verified by an empty plan/dry-run diff + a policy engine, with human gates on destructive changes.",
    "cost-optimization": "Cut measured cost of a workload or LLM pipeline one lever at a time, verified by a real cost meter while a frozen SLO or quality bar keeps holding — never averaged.",
    "compliance-audit": "Remediate a system against a frozen policy-as-code control set, verified by the policy engine or evidence checker, honest that automated controls are a floor and attestations remain open.",
    "doc-verification": "Keep docs truthful against the code — every example runs, every documented symbol matches the real signature — verified by an example-runner or introspection diff, not a read-through.",
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
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(?:text)?[ \t]*\n(.*?)\n[ \t]*\1[ \t]*$", re.S | re.M)
PLACEHOLDER_RE = re.compile(r"<[^>\n]{1,50}>")


def _field(block: str, name: str) -> str:
    m = re.search(rf"^-\s+\*\*{re.escape(name)}:\*\*\s*(.+)$", block, re.M)
    return m.group(1).strip() if m else ""


STOP_ARM_NAMES = ("SUCCESS", "BUDGET", "NO-PROGRESS", "BLOCKED")
STOP_ARM_RE = re.compile(
    r"(^|[·|;])\s*(SUCCESS|BUDGET|NO-PROGRESS|BLOCKED)\b"
)


def parse_stop_arms(stop: str) -> dict:
    """Anchor on the arm names and slice each description up to the next arm.

    Robust to separator style (':', '—', '-'), arm ordering, and descriptions
    that themselves contain '·' — which naive splitting broke on. Handles the
    Chinese self-critique family (arm names stay English, descriptions Chinese).
    """
    positions = [(m.start(2), m.end(), m.group(2)) for m in STOP_ARM_RE.finditer(stop)]
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


def _explicit_verifier_text(prompt_text: str) -> str:
    """Return the first explicit VERIFIER: clause/paragraph, if present."""
    m = re.search(
        r"(?i)\b(?:INDEPENDENT\s+)?VERIFIER\s*:\s*(.+?)(?=\n\s*\n|\s+(?:LOOP|PER-TURN|CARRY|STOP)\s*:|\Z)",
        prompt_text,
        re.S,
    )
    return m.group(1).strip() if m else ""


# Verifier keyword lists — module constants so the Python engine AND the
# client-side /lab & /compare analyzer share ONE source of truth (emitted via
# analysis_rules()). Mechanical = execution ground-truth; judge = model/rubric.
MECH_KEYWORDS = (
    "test suite", "benchmark", "schema valid", "json schema", "compiler",
    "compile", "validator", "diff tool", "scanner", "coverage tool",
    "exit code", "back-translation", "field f1", "pass count", "golden",
    "run the test", "same test command", "reproduces the reported failure",
    "run in ci", "test command", "checker", "harness", "ocr",
    "run the script", "re-run the", "reproduce the",
)
JUDGE_KEYWORDS = (
    "rubric", "judge", "persona", "fresh-reader", "fresh reader",
    "self-critique", "re-reads", "reviewer", "grade", "human review",
    "llm-with-vision", "scor",
)


# Keywords must match at a word start. Plain substring matching read "grade" inside
# "upgrade"/"downgrade" and labelled 7 prompts as having a judge/rubric verifier purely
# because they mentioned upgrading. The boundary is spelled with an explicit character
# class rather than \b because the JS mirror must agree exactly, and \b disagrees
# between Python (unicode-aware) and JavaScript (ASCII-only) next to CJK text.
KEYWORD_BOUNDARY = r"(?:^|[^a-z0-9])"


def _keyword_hit(blob: str, keywords) -> bool:
    return any(re.search(KEYWORD_BOUNDARY + re.escape(k), blob) for k in keywords)


def derive_verifier_type(model: str, prompt_text: str) -> str:
    """Honest facet: mechanical (execution ground-truth) vs judge (model/rubric)."""
    explicit = _explicit_verifier_text(prompt_text)
    blob = (model + " " + (explicit or prompt_text)).lower()
    mechanical = _keyword_hit(blob, MECH_KEYWORDS)
    judge = _keyword_hit(blob, JUDGE_KEYWORDS)
    if mechanical and not judge:
        return "mechanical"
    if judge and not mechanical:
        return "judge"
    if mechanical and judge:
        return "mixed"
    if explicit:
        return "mechanical"
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
        prompt_text = fence.group(2).strip() if fence else ""
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
    # Scope strictly to the "## Principles" section: everything between that heading
    # and "## Antipatterns". Previously this scanned the whole file and then sliced
    # to a hardcoded count, which silently dropped principle #12 from the site.
    section = text
    if "## Principles" in section:
        section = section.split("## Principles", 1)[1]
    section = section.split("## Antipatterns", 1)[0]
    for pm in re.finditer(r"^-\s+\*\*(.+?)\*\*\s*—\s*(.+)$", section, re.M):
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
    principles = [p for p in principles if "—" not in p["name"]]
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
# test-gen, review, prompt-opt families), so anchor-splitting handles the corpus
# uniformly where paragraph-splitting collapsed a whole prompt into one block.
_ANCHORS: list[tuple[str, str]] = [
    ("goal", r"GOAL \(frozen\)|Goal \(frozen\)|Frozen goal|GOAL:|Goal:|"
             r"Freeze the goal[^:.\n]*|Freeze the claim[^:.\n]*|Freeze the finding[^:.\n]*|"
             r"Freeze the conclusion[^:.\n]*|Freeze the thesis[^:.\n]*|Freeze the stated[^:.\n]*|"
             r"Freeze the root[^:.\n]*|Freeze this[^:.\n]*|Before turn 1, freeze[^:.\n]*|Target:"),
    ("verifier", r"(?:INDEPENDENT\s+)?VERIFIER\b(?=\s*[:(—-])|Independent checker|Independent validator"),
    ("action", r"LOOP \(each turn\)|LOOP:|Each turn|Each round|Per turn|PER-TURN SHAPE|"
               r"Turn shape|Every turn|First turn|Baseline first|Start by"),
    ("state", r"Carry forward|CARRY-FORWARD STATE|Carry state|Carry compact|Maintain a |Maintain this |State log"),
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
        for m in re.finditer(pat, text, re.I):
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
    if "_patterns" in p:
        return p["_patterns"]
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
    p["_patterns"] = found
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


def analysis_rules() -> dict:
    """Serialize the deterministic analysis engine's rule tables for the client-side
    /lab & /compare analyzer, so the browser mirrors this module without a second
    source of truth. Regex sources are authored JS-compatible (RegExp)."""
    return {
        "anatLabels": ANAT_LABELS,
        "anatOrder": ANAT_ORDER,
        "anchors": [[role, src] for role, src in _ANCHORS],  # compiled 'gi' client-side
        # explicit VERIFIER: clause — JS-adapted (dotAll via [\s\S], \Z -> $)
        "explicitVerifier": r"\b(?:INDEPENDENT\s+)?VERIFIER\s*:\s*([\s\S]+?)(?=\n\s*\n|\s+(?:LOOP|PER-TURN|CARRY|STOP)\s*:|$)",
        "keywordBoundary": KEYWORD_BOUNDARY.replace("(?:", "(") ,  # JS has no (?: need here
        "mechKw": list(MECH_KEYWORDS),
        "judgeKw": list(JUDGE_KEYWORDS),
        "patternMeta": [[k, n, r, b] for k, n, r, b in PATTERN_META],
        "stopArms": list(STOP_ARM_NAMES),
    }


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
    # Sort: a set's iteration order depends on PYTHONHASHSEED, which made the
    # generated site differ byte-for-byte between runs of identical input.
    return {k: sorted(v) for k, v in edges.items()}


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

def absolute_url(path: str) -> str:
    clean = path.lstrip("/")
    if clean in ("", "index.html"):
        return BASE_URL.rstrip("/") + "/"
    return urljoin(BASE_URL, clean)


CHROME_SCRIPT = (
    "document.documentElement.classList.add('js');"
    "try{if(!matchMedia('(prefers-reduced-motion: reduce)').matches)"
    "document.documentElement.classList.add('motion-ok');}catch(e){}"
)

# Inline <script> blocks without a src attribute; each needs its own CSP hash.
_INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)


def _script_hash(source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def csp_for(*chunks: str) -> str:
    """A per-page Content-Security-Policy that allowlists exactly this page's inline
    scripts by hash. There was previously no CSP at all, so any future escaping slip
    in an innerHTML sink had no backstop.

    style-src-attr keeps 'unsafe-inline' only because a handful of generated elements
    carry a style="" attribute; inline <style> blocks and inline scripts stay blocked.
    """
    hashes = [_script_hash(CHROME_SCRIPT)]
    for chunk in chunks:
        for m in _INLINE_SCRIPT_RE.finditer(chunk or ""):
            h = _script_hash(m.group(1))
            if h not in hashes:
                hashes.append(h)
    return (
        "default-src 'none'; "
        f"script-src 'self' {' '.join(hashes)}; "
        "style-src 'self'; style-src-attr 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        # frame-ancestors is deliberately absent: it is IGNORED in a <meta> CSP and
        # logs an error on every page. Clickjacking protection needs a real HTTP
        # header (X-Frame-Options / frame-ancestors), which GitHub Pages cannot set.
        "base-uri 'none'; form-action 'none'"
    )


def page(title: str, body: str, prefix: str, *, desc: str, path: str, extra_head: str = "") -> str:
    prompt_count = CORPUS_PROMPT_COUNT or "All"
    description = re.sub(r"\s+", " ", desc).strip()
    if not description:
        raise ValueError(f"empty meta description for {path}")
    url = absolute_url(path)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp_for(body, extra_head)}">
<script>{CHROME_SCRIPT}</script>
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="canonical" href="{html.escape(url)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{html.escape(url)}">
<meta property="og:site_name" content="prompt-os">
<meta property="og:image" content="{html.escape(absolute_url('assets/og.png'))}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{html.escape(absolute_url('assets/og.png'))}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%233a4ce0'/%3E%3Cpath d='M11 16a5 5 0 1 1 5 5' fill='none' stroke='white' stroke-width='3' stroke-linecap='round'/%3E%3Cpath d='M16 17l-5 4v-8z' fill='white'/%3E%3C/svg%3E">
<link rel="stylesheet" href="{prefix}assets/style.css?v={ASSET_VER}">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap head-inner">
    <a class="brand" href="{prefix}index.html">prompt<span>·</span>os</a>
    <nav aria-label="Primary">
      <a href="{prefix}find.html">Find</a>
      <a href="{prefix}lab.html">Lab</a>
      <a href="{prefix}compare.html">Compare</a>
      <a href="{prefix}learn.html">Learn</a>
      <span class="nav-sep" aria-hidden="true"></span>
      <a href="{prefix}library.html">Library</a>
      <a href="{prefix}patterns.html">Patterns</a>
      <a href="{prefix}graph.html">Graph</a>
      <a href="{prefix}loops.html">Loops</a>
      <a href="{prefix}automation.html">Automation</a>
      <a href="{prefix}families.html">Families</a>
      <a href="{prefix}anatomy.html">Anatomy</a>
      <a href="{prefix}evolve.html">Evolve</a>
      <a href="{prefix}glossary.html">Glossary</a>
    </nav>
  </div>
</header>
<main id="main" tabindex="-1">
{body}
</main>
<div id="copyStatus" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>
<footer class="site-foot">
  <div class="wrap">
    <p>{prompt_count} agent-loop prompts · {len(FAMILIES)} families · one shared anatomy.
    Content from the <strong>prompt-os</strong> loop library — generated by a
    multi-agent authoring process with adversarial verification, human-reviewed. Every prompt has an
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


def json_for_script(value) -> str:
    """Serialize data for an inline script without allowing data to close the tag."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def write_sitemap_and_robots() -> int:
    html_paths = sorted(SITE.rglob("*.html"))
    urls = [absolute_url(path.relative_to(SITE).as_posix()) for path in html_paths]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(url)}</loc></url>\n" for url in urls)
        + "</urlset>\n"
    )
    (SITE / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (SITE / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {absolute_url('sitemap.xml')}\n",
        encoding="utf-8",
    )
    return len(urls)


def facet_chips(p: dict) -> str:
    out = [chip(p["family_title"], "chip-family")]
    if p["starter"]:
        out.append(chip("starter", "chip-starter"))
    vt = p["verifier_type"]
    if vt in ("mechanical", "judge", "mixed"):
        out.append(chip(f"{vt} verifier", f"chip-verifier chip-{vt}"))
    else:
        out.append(chip("verifier not detected", "chip-verifier chip-unspecified"))
    out.append(chip(f"{p['model_hint']} model", "chip-model"))
    return "".join(out)


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")


def lang_attr(text: str, lang: str = "zh-Hans") -> str:
    """' lang="zh-Hans"' when the text contains CJK, else ''.

    Two families (self-critique, orchestration-harness) are authored in Chinese while
    every page declares lang="en", so assistive tech applies English phonetics to
    Mandarin. Annotating the containing element is the minimum correct fix and
    changes no content.
    """
    return f' lang="{lang}"' if CJK_RE.search(text or "") else ""


def card_title_html(p: dict, num: bool = False) -> str:
    """Card title: English display line, with the non-ASCII original muted beneath."""
    label = f'{p["num"]}. {p["display_title"]}' if num else p["display_title"]
    out = f'<span class="pcard-title"{lang_attr(label)}>{html.escape(label)}</span>'
    if p["alt_title"]:
        out += (f'<span class="pcard-alt"{lang_attr(p["alt_title"])}>'
                f'{html.escape(p["alt_title"])}</span>')
    return out


def loop_steps_html(loop: str) -> str:
    steps = [s.strip() for s in re.split(r"\s*->\s*|\s*→\s*", loop) if s.strip()]
    return ('<ol class="loop-steps">'
            + "".join(f"<li{lang_attr(s)}>{html.escape(s)}</li>" for s in steps)
            + "</ol>")


def stop_arms_html(arms: dict) -> str:
    order = [("SUCCESS", "arm-success"), ("BUDGET", "arm-budget"),
             ("NO-PROGRESS", "arm-noprogress"), ("BLOCKED", "arm-blocked")]
    rows = []
    for name, cls in order:
        if name in arms:
            rows.append(f'<div class="stoparm {cls}"><span class="arm-name">{name}</span>'
                        f'<span class="arm-body"{lang_attr(arms[name])}>'
                        f'{html.escape(arms[name])}</span></div>')
    return '<div class="stoparms">' + "".join(rows) + "</div>"


# ---- Detail page ------------------------------------------------------------

def render_detail(p: dict, related_list: list) -> str:
    prefix = "../"
    esc_prompt = html.escape(p["prompt_text"])
    tab_prefix = p["id"]

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

    skill_payload = {
        "name": p["id"], "title": p["display_title"], "when": p["when"],
        "family": p["family_title"], "model": p["model"], "body": p["prompt_text"],
    }

    body = f"""
<div class="wrap detail">
  <p class="crumbs"><a href="{prefix}library.html">Library</a> ›
     <a href="{prefix}family/{p['family_key']}.html">{html.escape(p['family_title'])}</a> ›
     <span>{html.escape(p['display_title'])}</span></p>

  <h1 class="detail-title"{lang_attr(p['display_title'])}>{html.escape(p['display_title'])}</h1>
  {f'<p class="detail-alt"{lang_attr(p["alt_title"])}>{html.escape(p["alt_title"])}</p>' if p['alt_title'] else ''}
  <p class="detail-when"{lang_attr(p['when'])}>{html.escape(p['when'])}</p>
  <div class="facets">{facet_chips(p)}</div>
  {f'<div class="patternrow"><span class="patternrow-label">Patterns</span>{pattern_chips}</div>' if pattern_chips else ''}

  <div class="tabs" role="tablist" aria-label="Prompt detail sections">
    <button class="tab is-active" id="{tab_prefix}-tab-prompt" data-tab="prompt" role="tab" aria-selected="true" aria-controls="{tab_prefix}-panel-prompt">Prompt</button>
    <button class="tab" id="{tab_prefix}-tab-anatomy" data-tab="anatomy" role="tab" aria-selected="false" aria-controls="{tab_prefix}-panel-anatomy">Anatomy</button>
    <button class="tab" id="{tab_prefix}-tab-why" data-tab="why" role="tab" aria-selected="false" aria-controls="{tab_prefix}-panel-why">Why it works</button>
    <button class="tab" id="{tab_prefix}-tab-source" data-tab="source" role="tab" aria-selected="false" aria-controls="{tab_prefix}-panel-source">Source</button>
  </div>

  <section class="tabpanel is-active" id="{tab_prefix}-panel-prompt" data-panel="prompt" role="tabpanel" aria-labelledby="{tab_prefix}-tab-prompt" tabindex="0">
    {vars_html}
    <div class="prompt-toolbar">
      <button class="copy-btn" data-copy-target="promptbody">Copy prompt</button>
      <span class="prompt-meta">{p['prompt_chars']} chars · {html.escape(p['length_bucket'])}</span>
    </div>
    <pre class="promptbody" id="promptbody"{lang_attr(p["prompt_text"])}>{esc_prompt}</pre>
    {complexity_html}

    <h2 class="sub">The loop</h2>
    {loop_steps_html(p['loop'])}
    <h2 class="sub">Stop condition <span class="muted">(halts on the first that trips)</span></h2>
    {stop_arms_html(p['stop_arms'])}
    <h2 class="sub">Model routing</h2>
    <p class="model-note"{lang_attr(p['model'])}>{html.escape(p['model'])}</p>
  </section>

  <section class="tabpanel" id="{tab_prefix}-panel-anatomy" data-panel="anatomy" role="tabpanel" aria-labelledby="{tab_prefix}-tab-anatomy" tabindex="0">
    <p class="lead">Every prompt in this library shares one shape. The colored blocks below are the
    prompt's own paragraphs, labeled by the role they play in the loop.
    <a href="{prefix}anatomy.html">See the full anatomy →</a></p>
    <div class="anat-legend">
      {"".join(f'<span class="anat-key anat-dot-{k}">{ANAT_LABELS[k]}</span>' for k in ANAT_ORDER)}
    </div>
    {render_anatomy(p['prompt_text'], reveal=True)}
  </section>

  <section class="tabpanel" id="{tab_prefix}-panel-why" data-panel="why" role="tabpanel" aria-labelledby="{tab_prefix}-tab-why" tabindex="0">
    <p class="lead">Not marketing — mechanism. Each principle below is one this prompt
    <em>actually</em> exhibits, quoted from its own text:</p>
    {why_html}
    <h2 class="sub">This prompt's four exits</h2>
    <p class="lead">It can only end one way — whichever of these trips first:</p>
    {stop_arms_html(p['stop_arms'])}
    <p class="muted">Read the underlying <a href="{prefix}anatomy.html">principles and antipatterns →</a>,
    or look up a term in the <a href="{prefix}glossary.html">glossary →</a></p>
  </section>

  <section class="tabpanel" id="{tab_prefix}-panel-source" data-panel="source" role="tabpanel" aria-labelledby="{tab_prefix}-tab-source" tabindex="0">
    <dl class="source-dl">
      <dt>Collection</dt><dd>prompt-os loop library — this repository, family <code>{p['family_key']}</code>, prompt #{p['num']}.</dd>
      <dt>Method</dt><dd>Generated by multi-agent authoring with adversarial verification, then human-reviewed.</dd>
      <dt>Original / derived</dt><dd>Original — independently authored loop template, not copied from an external collection.</dd>
      <dt>License</dt><dd>MIT — see LICENSE. Reuse the prompt text freely; keep this provenance note if you republish.</dd>
      <dt>Verifier type</dt><dd>{html.escape(p['verifier_type'])} — {'execution/ground-truth signal' if p['verifier_type']=='mechanical' else 'model/rubric judgment' if p['verifier_type']=='judge' else 'both mechanical and judged signals' if p['verifier_type']=='mixed' else 'not clearly specified'}.</dd>
    </dl>
    <div class="skill-export">
      <button class="btn btn-ghost" id="skillExport" type="button">⤓ Export as Claude Code skill</button>
      <span class="skill-hint">saves <code>{html.escape(p['id'])}.md</code> → put it at <code>~/.claude/skills/{html.escape(p['id'])}/SKILL.md</code></span>
    </div>
    {dup_html}
  </section>

  {related_html}
</div>
<script>window.__SKILL__={json_for_script(skill_payload)};</script>
"""
    return page(f"{p['display_title']} · prompt-os", body, prefix,
                desc=p["when"][:180],
                path=f"prompt/{p['id']}.html")


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
        f'<span class="pcard-when"{lang_attr(p["when"])}>{html.escape(p["when"][:120])}…</span>'
        f'<span class="pcard-foot">{facet_chips(p)}</span></a>'
        for p in starters
    )
    body = f"""
<section class="hero hero-dark">
  <div class="hero-stars" aria-hidden="true"></div>
  <div class="hero-aurora" aria-hidden="true"></div>
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="kicker">prompt-os · loop-prompt library</p>
      <h1>Understand how powerful AI prompts <span class="hl-hand">actually work</span>.</h1>
      <p class="sub">Explore {stats['total']} verified prompts — their internal anatomy, validation
      systems, loops, stopping conditions, and automation patterns. Every one is a
      <em>frozen goal → one action → independent verifier → multi-armed stop</em>.</p>
      <p class="hero-icp">For engineers building AI agents and loops: a working reference for prompts that
      <strong>finish, check their own work, and can't loop forever</strong> — and a
      <a href="lab.html">Lab</a> to X-ray your <em>own</em> prompt the same way.</p>
      <div class="cta-row">
        <a class="btn btn-primary" href="find.html">Find your prompt</a>
        <a class="btn btn-ghost" href="lab.html">Analyze your prompt</a>
        <a class="btn btn-ghost" href="library.html">Browse the library</a>
      </div>
    </div>
    <div class="hero-viz" id="heroViz">
      <canvas class="hero-gl" id="heroGL" aria-hidden="true" hidden></canvas>
      <div class="hero-gl-fallback" id="heroFallback">{hero_ring_svg()}</div>
      <p class="hero-loop-cap" aria-hidden="true"><span>goal</span><span>action</span><span>verify</span><span>decide</span><span>stop</span></p>
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
                desc=f"{stats['total']} agent-loop prompts across {stats['families']} families, each with an explicit stop condition. "
                     "Learn the anatomy of reliable AI loops.",
                path="index.html")


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
  <p class="section-sub">The reusable structures underneath the {stats['total']} prompts — detected mechanically,
  counted across the whole corpus. The number is how many prompts use each.</p>
  <div class="pat-grid">{"".join(rows)}</div>
</section>
"""
    return page("Patterns · prompt-os", body, "",
                desc="The reusable loop patterns across the prompt-os corpus, with usage counts — "
                     "commit/revert, human escalation, adversarial verification, fan-out, ratchet, and more.",
                path="patterns.html")


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
        extra = f'<h2 class="section-h">Use guidance</h2><div class="pat-blocks">{blocks}</div>'

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
                desc=definition[:180],
                path=f"pattern/{key}.html")


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
        f'<button class="lv-preset{" active" if k == first else ""}" data-k="{k}" '
        f'aria-pressed="{"true" if k == first else "false"}">{html.escape(nm)}</button>'
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

  <div class="lv-presets" aria-label="Loop presets">{presets}</div>

  <div class="loopviz" tabindex="0" role="region" aria-label="Interactive loop visualizer" aria-describedby="lv-help">
    <div class="lv-stage">
      <div class="lv-ring-wrap"></div>
      <div class="lv-panel" aria-live="polite" aria-atomic="true">
        <div class="lv-step-label">Step</div>
        <div class="lv-step-title">—</div>
        <div class="lv-step-desc"></div>
        <div class="lv-quote" hidden></div>
        <div class="lv-exits"></div>
        <p id="lv-help" class="muted" style="margin-top:14px;font-size:.82rem">Exit conditions halt the loop on the first that trips. Use Previous and Next, or focus this region and use Left/Right arrows.</p>
      </div>
    </div>
    <div class="lv-controls">
      <button class="lv-btn primary lv-play" aria-pressed="false">▶ Play</button>
      <button class="lv-btn lv-prev">‹ Previous</button>
      <button class="lv-btn lv-next">Next ›</button>
      <button class="lv-btn lv-restart">↻ Restart</button>
      <button class="lv-btn lv-speed" aria-label="Playback speed: 1 times">1×</button>
    </div>
    <ol class="lv-fallback">{fallback}</ol>
  </div>
</section>
<script>window.LOOPVIZ = {json_for_script(viz)};</script>
"""
    return page("Loops · prompt-os", body, "",
                desc="Interactive loop visualizer — step through real agent loops (research, coding, "
                     "prompt-improvement, debugging) and see their SUCCESS/BUDGET/NO-PROGRESS/BLOCKED exits.",
                path="loops.html")


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
    <select id="g-family" class="filter" aria-label="Filter graph by family"><option value="">All families</option>{fam_opts}</select>
    <button class="lv-btn" id="g-reset">Reset</button>
    <span class="graph-hint muted">Tip: hover = highlight relatives · click = open</span>
  </div>
  <div class="graph-stage">
    <div class="graph-wrap" id="graphWrap" role="region" aria-label="Constellation of {len(data['nodes'])} prompts clustered by family"></div>
    <aside class="graph-panel" id="graphPanel" hidden></aside>
  </div>
  <details class="graph-fallback"><summary>Browse as a list instead</summary>{fallback}</details>
</section>
<script>window.GRAPH = {json_for_script(data)};</script>
"""
    return page("Constellation · prompt-os", body, "",
                desc="An interactive constellation of every prompt, clustered by family, with real "
                     "relationship edges from shared patterns and curation near-duplicates.",
                path="graph.html")


# ---- Prompt evolution -------------------------------------------------------
# A curated teaching progression: one instruction gaining one anatomy layer per
# stage. Authored here (accurate, grounded in the loop principles), not generated.
# New content at each stage is wrapped in [[...]] and rendered as <ins>.
EVOLUTION = [
    {"name": "Rough request", "role": None,
     "adds": "nothing yet — just an ask",
     "why": "It has no definition of done, no output shape, and no way to check the result. The model guesses what you meant and stops whenever it feels finished.",
     "text": "Research this topic and tell me what you find."},
    {"name": "Structured", "role": "goal",
     "adds": "goal · scope · output format",
     "why": "Now the task, the boundary, and the deliverable are explicit — the model isn't guessing the shape of a good answer.",
     "text": "Research [[<TOPIC>, focused on <ANGLE>]]. [[Return a 5-point summary; each point is one sentence with a source link.]]"},
    {"name": "Verified", "role": "verifier",
     "adds": "source rules · an independent check",
     "why": "A claim only counts if an independent source backs it. This is the difference between a confident-sounding answer and a checked one.",
     "text": "Research <TOPIC>, focused on <ANGLE>. Return a 5-point summary; each point is one sentence with a source link. [[Every point must be corroborated by an independent source; if you can't corroborate one, drop it or mark it UNVERIFIED. Prefer primary sources.]]"},
    {"name": "Looping", "role": "action",
     "adds": "frozen goal · per-turn loop · saturation stop",
     "why": "One search is rarely enough. The loop keeps closing gaps and — crucially — stops on evidence saturation, not on a fixed count or on the model getting tired.",
     "text": "[[Goal (frozen): a 5-point, fully-sourced summary of <TOPIC>/<ANGLE> where no point is UNVERIFIED.]] [[Each turn: search → read → extract candidate points → verify each against an independent source → note gaps → search again for the gaps.]] [[Stop when two consecutive searches surface no new corroborated point (saturation).]]"},
    {"name": "Production", "role": "stop",
     "adds": "compact state · 4-arm stop · budget · recovery · logging",
     "why": "The multi-armed stop means it can never run forever or grind silently: it halts on success, budget, no-progress, OR a block — and hands off cleanly when it needs a human.",
     "text": "Goal (frozen): a 5-point, fully-sourced summary of <TOPIC>/<ANGLE>, no point UNVERIFIED, verified by an independent corroboration check. Each turn: assess the point ledger → ONE search or ONE verification → update the ledger → decide. [[Carry forward: the point ledger (point | status | source), searches tried, budget left.]] [[Stop on the FIRST of: SUCCESS — 5 corroborated points, none UNVERIFIED; BUDGET — <MAX_SEARCHES> searches; NO-PROGRESS — no new corroborated point for 3 turns; BLOCKED — a required source is paywalled/unavailable.]] [[Log each turn's ledger; on BLOCKED or NO-PROGRESS, hand off with what's been tried.]]"},
]


def _evolution_text_html(text: str) -> str:
    # escape, then turn [[...]] markers into highlighted <ins> spans
    out, i = [], 0
    for m in re.finditer(r"\[\[(.+?)\]\]", text, re.S):
        out.append(html.escape(text[i:m.start()]))
        out.append(f'<ins>{html.escape(m.group(1))}</ins>')
        i = m.end()
    out.append(html.escape(text[i:]))
    return "".join(out)


def render_evolution() -> str:
    dots, steps = "", ""
    for i, s in enumerate(EVOLUTION):
        dots += (f'<button class="ev-dot" id="ev-tab-{i}" data-i="{i}" role="tab" '
                 f'aria-selected="{"true" if i == 0 else "false"}" aria-controls="ev-panel-{i}" '
                 f'aria-label="Stage {i+1}: {html.escape(s["name"])}">'
                 f'<span class="ev-dot-n">{i+1}</span><span class="ev-dot-name">{html.escape(s["name"])}</span></button>')
        steps += (
            f'<article class="ev-stage" id="ev-panel-{i}" data-i="{i}" role="tabpanel" '
            f'aria-labelledby="ev-tab-{i}" tabindex="0"{" data-active" if i == 0 else ""}>'
            f'<div class="ev-head"><span class="ev-num">Stage {i+1}</span>'
            f'<h2>{html.escape(s["name"])}</h2>'
            f'<span class="ev-adds">adds: {html.escape(s["adds"])}</span></div>'
            f'<pre id="evpre{i}" class="ev-text">{_evolution_text_html(s["text"])}</pre>'
            f'<div class="ev-toolbar"><button class="copy-btn" data-copy-target="evpre{i}">Copy this version</button>'
            f'<span class="ev-hint muted">highlighted = new at this stage</span></div>'
            f'<p class="ev-why">{html.escape(s["why"])}</p>'
            f'</article>'
        )
    body = f"""
<section class="wrap evolution-page">
  <h1 class="section-h">Watch a prompt evolve</h1>
  <p class="section-sub">The same instruction, gaining one layer of loop anatomy at a time — from a vague
  ask to a production loop that can't run forever or lie about being done. Step through the stages; the
  <ins>highlighted</ins> text is what's new at each one.</p>
  <div class="ev-dots" role="tablist">{dots}</div>
  <div class="ev-stages">{steps}</div>
  <p class="muted" style="margin-top:22px">Every prompt in the <a href="library.html">library</a> lives at
  the last stage. See the parts named on the <a href="anatomy.html">anatomy page</a>.</p>
</section>
"""
    return page("Evolve · prompt-os", body, "",
                desc="Watch one instruction evolve from a rough request into a production agent loop, "
                     "gaining goal, verifier, loop, and a multi-armed stop one stage at a time.",
                path="evolve.html")


# ---- Prompt finder ----------------------------------------------------------

def render_find() -> str:
    examples = [
        "debug a flaky test that fails intermittently",
        "research a market before a big decision",
        "extract structured data from invoices",
        "get a fully-cited answer from my documents",
        "refactor code without changing behavior",
        "generate a product photo to a brand spec",
        "write SQL and check the result is right",
        "drive a browser to fill and submit a form",
    ]
    ex = "".join(f'<button class="find-ex" type="button" data-q="{html.escape(e)}">{html.escape(e)}</button>'
                 for e in examples)
    body = f"""
<section class="wrap find-page">
  <h1 class="section-h">Find your prompt</h1>
  <p class="section-sub">Describe what you want the AI to do, in plain language. This ranks all
  {CORPUS_PROMPT_COUNT} verified prompts by how well they fit your need and shows the best match —
  entirely in your browser, no account, no data sent anywhere.</p>
  <div class="find-box">
    <label class="sr-only" for="findQ">Describe what you need</label>
    <textarea id="findQ" class="find-input" rows="3"
      placeholder="e.g. I need to debug a flaky test that only fails sometimes…"></textarea>
    <button class="btn btn-primary find-go" id="findGo" type="button">Find the best prompt →</button>
  </div>
  <div class="find-examples"><span class="muted">Try:</span> {ex}</div>
  <div id="findResults" class="find-results" aria-live="polite"></div>
  <p class="find-fallback muted">Prefer to browse? Use the <a href="library.html">full library</a> with filters,
  or explore <a href="graph.html">the constellation</a>.</p>
</section>
"""
    return page("Find your prompt · prompt-os", body, "",
                desc="Describe what you want the AI to do and get the best-matching agent-loop prompt, "
                     "ranked across the whole verified corpus — client-side, no account.",
                path="find.html")


# ---- Lab: analyze your own prompt -------------------------------------------

def render_lab() -> str:
    """Paste any prompt; the SAME deterministic engine that powers the corpus
    (anatomy / patterns / verifier / complexity / why) runs on it in the browser."""
    example_ids = ["build-verify-1", "debug-rootcause-1", "research-until-dry-1"]
    ex = "".join(
        f'<button class="lab-ex" type="button" data-id="{html.escape(i)}">{html.escape(i)}</button>'
        for i in example_ids
    )
    legend = "".join(f'<span class="anat-key anat-dot-{k}">{ANAT_LABELS[k]}</span>' for k in ANAT_ORDER)
    body = f"""
<section class="wrap lab-page">
  <h1 class="section-h">Prompt Lab</h1>
  <p class="section-sub">Paste <em>your own</em> agent-loop prompt. The same deterministic engine that
  analyzes the {CORPUS_PROMPT_COUNT}-prompt library runs on it right here in your browser — it segments the
  <a href="anatomy.html">loop anatomy</a>, detects recurring <a href="patterns.html">patterns</a>, classifies the
  verifier, scores structural complexity, and explains why it works. No account, nothing sent anywhere.</p>
  <div class="lab-box">
    <label class="sr-only" for="labInput">Paste your prompt</label>
    <textarea id="labInput" class="lab-input" rows="10" spellcheck="false"
      placeholder="Paste an agent-loop prompt here — ideally one with a frozen goal, an independent verifier, one action per turn, and a stop condition (SUCCESS / BUDGET / NO-PROGRESS / BLOCKED)…"></textarea>
    <div class="lab-actions">
      <button class="btn btn-primary" id="labGo" type="button">Analyze this prompt →</button>
      <button class="btn btn-ghost" id="labClear" type="button">Clear</button>
      <span class="lab-load muted">or load an example: {ex}</span>
    </div>
  </div>
  <div class="anat-legend lab-legend" hidden>{legend}</div>
  <div id="labResults" class="lab-results" aria-live="polite"></div>
  <div id="labRewrite" class="lab-rewrite" hidden>
    <button class="btn btn-ghost" id="labRewriteBtn" type="button">✎ Rewrite as a compliant loop →</button>
    <div id="labRewriteOut" class="lab-rewrite-out" aria-live="polite"></div>
  </div>
  <p class="lab-note muted">Heuristic, not a grader — it reports the structure it can detect and flags what's
  missing (e.g. no independent verifier, no stop arms). It works best on loop/agent prompts; a generic
  “act as X” prompt has little loop structure to find, and the analysis will honestly say so. The rewrite is a
  <strong>scaffold</strong> generated in your browser — your content slotted into the canonical loop shape with the
  gaps marked <code>&lt;FILL: …&gt;</code>, not an AI-written finished prompt.</p>
</section>
"""
    return page("Prompt Lab · prompt-os", body, "",
                desc="Paste your own agent-loop prompt and get an instant, client-side anatomy / pattern / "
                     "verifier / complexity analysis from the same engine that powers the prompt-os library.",
                path="lab.html")


# ---- Compare: two prompts side by side --------------------------------------

def render_compare() -> str:
    """Pick two corpus prompts (or paste your own) and diff their loop structure."""
    body = f"""
<section class="wrap compare-page">
  <h1 class="section-h">Compare two prompts</h1>
  <p class="section-sub">Put two agent-loop prompts side by side and see how their structure differs —
  shared vs unique <a href="patterns.html">patterns</a>, verifier type, complexity, the four exits, and the
  full colour-coded <a href="anatomy.html">anatomy</a>. Pick from the {CORPUS_PROMPT_COUNT}-prompt library, or paste
  your own into either side. All in your browser.</p>
  <div class="cmp-pickers">
    <div class="cmp-pick">
      <label for="cmpSelA">Prompt A</label>
      <select id="cmpSelA" class="cmp-select"><option value="">— choose from library —</option></select>
      <details class="cmp-paste"><summary>or paste your own</summary>
        <textarea id="cmpTextA" class="lab-input" rows="6" spellcheck="false" aria-label="Paste prompt A" placeholder="Paste prompt A…"></textarea>
      </details>
    </div>
    <div class="cmp-pick">
      <label for="cmpSelB">Prompt B</label>
      <select id="cmpSelB" class="cmp-select"><option value="">— choose from library —</option></select>
      <details class="cmp-paste"><summary>or paste your own</summary>
        <textarea id="cmpTextB" class="lab-input" rows="6" spellcheck="false" aria-label="Paste prompt B" placeholder="Paste prompt B…"></textarea>
      </details>
    </div>
  </div>
  <div class="cmp-actions"><button class="btn btn-primary" id="cmpGo" type="button">Compare →</button></div>
  <div id="cmpDiff" class="cmp-diff" aria-live="polite"></div>
  <div id="cmpResults" class="cmp-results"></div>
  <p class="lab-note muted">Same deterministic engine as the <a href="lab.html">Lab</a> — run on each side,
  then diffed. Great for seeing why two prompts that look similar behave differently.</p>
</section>
"""
    return page("Compare prompts · prompt-os", body, "",
                desc="Compare two agent-loop prompts side by side — shared vs unique patterns, verifier type, "
                     "complexity, stop arms, and full loop anatomy. Client-side, over the prompt-os library.",
                path="compare.html",
                extra_head='<link rel="preload" href="data/prompts.json" as="fetch" crossorigin>')


# ---- Learn: a grounded micro-course + quizzes -------------------------------

# Each lesson's teaching text is the REAL principle body from the principles doc
# (grounded, not fabricated); the quiz is authored but its answer is checkable
# against that same principle/antipattern. `principle` = keywords matching a
# principle name; `example` = how to pick a real corpus prompt to illustrate it.
LEARN_MODULES = [
    {"id": "what-is-a-loop", "title": "What is a loop?",
     "principle": ["per-turn shape"],
     "intro": "An agent-<em>loop</em> prompt isn't a one-shot instruction — it's a small, self-terminating "
              "control structure. Every prompt in this library shares one shape: a <strong>frozen goal</strong>, "
              "exactly <strong>one action per turn</strong>, an <strong>independent verifier</strong> that closes "
              "each turn, and a <strong>multi-armed stop</strong>. Learn those four parts and you can read — and "
              "write — any of them.",
     "example": {"family": "build-verify"},
     "quiz": {"q": "A loop prompt has four parts. Which of these is NOT one of them?",
              "options": ["A frozen goal", "One reversible action per turn",
                          "An independent verifier", "A promise to keep going until it's perfect"],
              "correct": 3,
              "explain": "“Keep going until it's perfect” is the #1 antipattern — “perfect” is never mechanically "
                         "true, so the loop never terminates. The fourth part is an explicit, multi-armed STOP."},
     "remedial": "The four parts are: frozen goal · one action/turn · independent verifier · multi-armed stop. A vague “until perfect” is exactly what has no stop.",
     "stretch": {"q": "What single change most reliably turns an open-ended “keep improving X” prompt into one that actually terminates?",
                 "options": ["Add a frozen, checkable goal + a multi-armed stop closed by an independent verifier",
                             "Tell it to try harder and be thorough", "Give it more few-shot examples", "Raise the token budget"],
                 "correct": 0,
                 "explain": "Termination comes from the structure: a goal that can be checked, an explicit stop, and an independent “done” signal — not from effort, examples, or budget."}},
    {"id": "frozen-goal", "title": "The frozen goal",
     "principle": ["frozen goal"],
     "example": {"id": "build-verify-1"},
     "quiz": {"q": "Why is the goal “frozen” at the start of the loop?",
              "options": ["So “done” means the same thing on turn 1 and turn 20",
                          "To make the loop run faster",
                          "So the model can redefine success if it's struggling",
                          "To use fewer tokens"],
              "correct": 0,
              "explain": "Freeze the goal so “done” can't drift. Redefining success downward mid-run — moving the "
                         "goalposts — is a named antipattern; a frozen, checkable goal is what prevents it."},
     "remedial": "“Frozen” = the exit target means the same thing on turn 1 and turn 20. It stops the model quietly lowering the bar to “win”.",
     "stretch": {"q": "A loop keeps reporting SUCCESS, yet the output quality visibly drifts downward over turns. The most likely cause is…",
                 "options": ["Moving the goalposts — success is being redefined downward mid-run",
                             "Too many stop arms", "The goal is too specific", "Not enough iterations"],
                 "correct": 0,
                 "explain": "If success can be re-defined mid-run, a loop can “succeed” while getting worse. A frozen, checkable goal is the fix."}},
    {"id": "one-action", "title": "One reversible action per turn",
     "principle": ["one reversible action"],
     "example": {"family": "refactor-safe"},
     "quiz": {"q": "Why exactly ONE reversible action per turn, instead of batching several edits?",
              "options": ["So any regression is attributable to one action and can be rolled back cleanly",
                          "Because a model can only change one thing at a time",
                          "To make the prompt shorter",
                          "It doesn't really matter"],
              "correct": 0,
              "explain": "Bundling edits destroys the observe→attribute signal: when verification fails you can't "
                         "tell which change broke it, and rollback becomes all-or-nothing."},
     "remedial": "One small reversible change per turn = you can attribute any regression to exactly one action and roll it back cleanly.",
     "stretch": {"q": "You batch five edits per turn to move faster; the turn's verification fails. What have you actually lost?",
                 "options": ["Attributability and a clean rollback — you can't tell which edit broke it",
                             "Nothing, it's just faster", "Some token savings", "The frozen goal"],
                 "correct": 0,
                 "explain": "Batching is the antipattern: a failed verify no longer points at one cause, and revert becomes all-or-nothing."}},
    {"id": "independent-verifier", "title": "Verify with an independent signal",
     "principle": ["independent signal"],
     "example": {"pattern": "mechanical-verifier"},
     "cta": '<a class="btn btn-ghost" href="lab.html">Paste your prompt into the Lab →</a> to see which verifier '
            'type it uses (or whether it names one at all).',
     "quiz": {"q": "Which of these is the antipattern called “self-grading”?",
              "options": ["A test suite decides pass/fail",
                          "The agent that produced the output also declares it correct",
                          "A separate judge scores it against a fixed rubric",
                          "A compiler checks that it builds"],
              "correct": 1,
              "explain": "Self-grading = the producer verifies its own work with no independent signal. The "
                         "mechanism that decides “done” must differ from the thing being optimized."},
     "remedial": "The thing that decides “done” must be separate from the thing being changed: tests, a scanner, a compiler, or a judge in a fresh frame.",
     "stretch": {"q": "You tuned a model against metric M, then cite M as proof the work is done. What's the flaw?",
                 "options": ["Goodhart — verifying with the exact signal you optimized against",
                             "M is set too strict", "You didn't run M enough times", "The goal isn't frozen"],
                 "correct": 0,
                 "explain": "Beware Goodhart: don't verify with the signal you optimized. Use an independent check (or a held-out signal) the optimization never saw."}},
    {"id": "stop-arms", "title": "The four stop arms",
     "principle": ["multi-armed"],
     "example": {"id": "debug-rootcause-1"},
     "quiz": {"q": "A loop with only a SUCCESS exit and no other arms is…",
              "options": ["Perfectly safe", "An infinite loop waiting to happen",
                          "Faster than a multi-armed loop", "The recommended design"],
              "correct": 1,
              "explain": "Halt on the FIRST arm that trips: SUCCESS, BUDGET (cap reached), NO-PROGRESS (metric "
                         "flat for K turns), or BLOCKED (needs a human/resource). Success-only can't reach success → runs forever."},
     "remedial": "Four arms: SUCCESS · BUDGET (cap) · NO-PROGRESS (metric flat K turns) · BLOCKED (needs a human/resource). Halt on the first that trips.",
     "stretch": {"q": "Which arm halts a loop whose metric has stalled, even though the budget isn't yet spent?",
                 "options": ["NO-PROGRESS", "SUCCESS", "BUDGET", "BLOCKED"],
                 "correct": 0,
                 "explain": "NO-PROGRESS fires when the target metric hasn't improved for K turns — catching a stuck loop before BUDGET would."}},
    {"id": "non-progress", "title": "Break non-progress; escalate, don't grind",
     "principle": ["non-progress"],
     "example": {"pattern": "anti-oscillation"},
     "quiz": {"q": "An agent keeps flipping between state A and state B while reporting “progress”. What is it, and what should happen?",
              "options": ["Oscillation — force a strategy change or halt",
                          "Normal exploration — let it continue",
                          "Success — it's converging", "Budget — just add more iterations"],
              "correct": 0,
              "explain": "That's oscillation (A→B→A). Ban verbatim retries — a retry must change approach — and "
                         "after ~3 failures fail loud and escalate with what was tried, rather than grind the budget."},
     "remedial": "Track the metric per turn. Flat for K turns, or an A→B→A cycle → force a strategy change or halt; after ~3 fails, escalate.",
     "stretch": {"q": "After a failed attempt, a retry is legitimate only if it…",
                 "options": ["changes approach — never a verbatim re-attempt of the same action",
                             "uses a larger model", "adds a sleep and tries again", "repeats exactly, hoping for a different result"],
                 "correct": 0,
                 "explain": "Ban verbatim repetition of a failed action: a retry must differ in approach, or you're just oscillating and burning budget."}},
    {"id": "antipatterns", "title": "Antipatterns & your own prompt",
     "principle": None,
     "antipatterns": True,
     "cta": '<a class="btn btn-primary" href="lab.html">Analyze your own prompt →</a> '
            '<a class="btn btn-ghost" href="compare.html">or compare two →</a>',
     "quiz": {"q": "Which of these is an antipattern that stops a loop from terminating usefully?",
              "options": ["Parking “while I'm here” ideas in a backlog",
                          "Scope creep / gold-plating discovered mid-loop",
                          "Committing on improvement, reverting on regression",
                          "Carrying compact state forward instead of the full transcript"],
              "correct": 1,
              "explain": "Scope creep / gold-plating is the antipattern — the loop should close the defined gap and "
                         "nothing else. The other three are exactly the good practices this course teaches."},
     "remedial": "Antipatterns share a theme: no stop, self-grading, vague goals, batching, scope creep, moving goalposts, context bloat. Close the defined gap and nothing else.",
     "stretch": {"q": "Passing the full raw transcript to the model every turn, instead of a compact running state, causes…",
                 "options": ["context bloat, drift, and lost budget",
                             "faster convergence", "stronger verification", "no effect"],
                 "correct": 0,
                 "explain": "Carry a distilled running state (goal, tried, current best, last verifier result, budget) forward — dumping the whole transcript bloats context and drifts."}},
]


def _learn_principle(principles: dict, keys) -> dict | None:
    for p in principles["principles"]:
        n = p["name"].lower()
        if all(k in n for k in keys):
            return p
    return None


def _learn_example(prompts: list[dict], spec: dict) -> dict | None:
    pid = spec.get("id")
    if pid:
        hit = next((p for p in prompts if p["id"] == pid), None)
        if hit:
            return hit
    pat = spec.get("pattern")
    if pat:
        hit = next((p for p in prompts if pat in detect_patterns(p)), None)
        if hit:
            return hit
    fam = spec.get("family")
    if fam:
        hit = next((p for p in prompts if p["family_key"] == fam), None)
        if hit:
            return hit
    return None


def render_learn(prompts: list[dict], principles: dict) -> str:
    total = len(LEARN_MODULES)
    lessons_html = []
    for i, m in enumerate(LEARN_MODULES, 1):
        # grounded teaching text: the real principle body, or the lesson's own intro/antipattern list
        concept = ""
        if m.get("intro"):
            concept += f"<p>{m['intro']}</p>"
        pr = _learn_principle(principles, m["principle"]) if m.get("principle") else None
        if pr:
            concept += (f'<blockquote class="learn-quote"><strong>{html.escape(pr["name"])}.</strong> '
                        f'{html.escape(pr["body"])}</blockquote>')
        if m.get("antipatterns"):
            aps = principles["antipatterns"][:8]
            concept += ('<p>The failure modes to recognize — a loop fails when it does any of these:</p>'
                        '<ul class="learn-aps">'
                        + "".join(f"<li>{html.escape(a)}</li>" for a in aps) + "</ul>")

        ex = _learn_example(prompts, m.get("example", {})) if m.get("example") else None
        ex_html = ""
        if ex:
            ex_html = (f'<div class="learn-ex"><span class="learn-ex-label">See it in a real prompt</span>'
                       f'<a class="learn-ex-card" href="prompt/{ex["id"]}.html">'
                       f'<span class="learn-ex-fam">{html.escape(ex["family_title"])}</span>'
                       f'<span class="learn-ex-title">{html.escape(ex["display_title"])}</span>'
                       f'<span class="learn-ex-when">{html.escape(ex["when"][:120])}…</span></a></div>')

        q = m["quiz"]
        opts = "".join(
            f'<button class="quiz-opt" type="button" data-i="{oi}">{html.escape(o)}</button>'
            for oi, o in enumerate(q["options"])
        )
        s = m["stretch"]
        sopts = "".join(
            f'<button class="quiz-opt" type="button" data-i="{oi}">{html.escape(o)}</button>'
            for oi, o in enumerate(s["options"])
        )
        cta_html = f'<p class="learn-cta">{m["cta"]}</p>' if m.get("cta") else ""
        lessons_html.append(f"""
<section class="lesson" id="lesson-{m['id']}" data-lesson="{m['id']}">
  <div class="lesson-head"><span class="lesson-num">{i}</span>
    <h2 class="lesson-title">{html.escape(m['title'])}</h2>
    <span class="lesson-done" hidden aria-hidden="true">✓ done</span>
    <span class="lesson-mastered" hidden aria-hidden="true">✦ mastered</span></div>
  <div class="lesson-body">
    {concept}
    {ex_html}
    <div class="quiz quiz-core" data-correct="{q['correct']}">
      <h3 class="quiz-h">Check yourself</h3>
      <p class="quiz-q">{html.escape(q['q'])}</p>
      <div class="quiz-opts" role="group" aria-label="Answer options">{opts}</div>
      <p class="quiz-explain" hidden>{q['explain']}</p>
    </div>
    <p class="quiz-remedial" hidden>💡 {html.escape(m.get('remedial',''))}</p>
    <div class="quiz quiz-stretch" data-correct="{s['correct']}" hidden>
      <h3 class="quiz-h">✦ Stretch — go deeper</h3>
      <p class="quiz-q">{html.escape(s['q'])}</p>
      <div class="quiz-opts" role="group" aria-label="Harder answer options">{sopts}</div>
      <p class="quiz-explain" hidden>{s['explain']}</p>
    </div>
    {cta_html}
  </div>
</section>""")

    body = f"""
<section class="wrap learn-page">
  <h1 class="section-h">Learn loop engineering</h1>
  <p class="section-sub">A short, grounded course in the one skill this whole library is about: turning a task into
  a reliable, self-terminating loop. {total} lessons, each with a real prompt from the corpus and a quick check.
  Everything below is drawn straight from the library's own <a href="anatomy.html">principles</a> — nothing invented.
  Progress is saved in your browser only.</p>
  <div class="learn-progress" role="status" aria-live="polite">
    <div class="learn-bar"><span class="learn-bar-fill" id="learnFill" style="width:0%"></span></div>
    <span class="learn-count" id="learnCount">0 of {total} checks complete</span>
    <span class="learn-level" id="learnLevel">Level: Foundations</span>
    <button class="learn-reset" id="learnReset" type="button" hidden>Reset progress</button>
  </div>
  <p class="learn-adapt muted">Answer a check and its <strong>✦ stretch</strong> question unlocks. Master stretch questions to
  level up — <strong>Practitioner</strong> unlocks the harder questions everywhere so the course keeps pace with you.</p>
  {''.join(lessons_html)}
  <p class="lab-note muted">Finished the checks? The real test is your own work — run a prompt of yours through the
  <a href="lab.html">Lab</a>, then read the underlying <a href="anatomy.html">anatomy</a> and
  <a href="glossary.html">glossary</a>.</p>
</section>
"""
    return page("Learn loop engineering · prompt-os", body, "",
                desc=f"A short, grounded {total}-lesson course in loop engineering — frozen goals, independent "
                     "verifiers, one action per turn, and multi-armed stops — with real prompts and quick quizzes.",
                path="learn.html")


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
                     "anomaly alerting, and more.",
                path="automation.html")


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
  <div class="run-status" id="autoStatus" role="status" aria-live="polite" aria-atomic="true"></div>
  <div class="flow" data-run>{flow}</div>

  <h2 class="section-h">Reliability</h2>
  {rel_html}

  {fail_html}

  <p class="muted">This is a reference shape to adapt, not a drop-in template — wire it to your own
  tools, and keep the human/validation gates where money or irreversible actions are involved.</p>
</section>
"""
    return page(f"{a['name']} · Automation · prompt-os", body, prefix, desc=goal[:180],
                path=f"automation/{a['key']}.html")


# ---- Library ----------------------------------------------------------------

def render_library() -> str:
    fam_opts = "".join(f'<option value="{k}">{html.escape(t)}</option>' for k, t in FAMILIES)
    body = f"""
<section class="wrap lib">
  <h1 class="section-h">Prompt library</h1>
  <p class="section-sub">All {CORPUS_PROMPT_COUNT} loop prompts. Filter and search — everything runs in your browser.</p>

  <div class="lib-controls">
    <input id="q" class="search" type="search" aria-label="Search prompts" placeholder="Search title, purpose, or prompt text…" autocomplete="off">
    <select id="f-family" class="filter" aria-label="Filter by family"><option value="">All families</option>{fam_opts}</select>
    <select id="f-verifier" class="filter" aria-label="Filter by verifier type">
      <option value="">Any verifier</option>
      <option value="mechanical">Mechanical (execution)</option>
      <option value="judge">Judge (rubric/model)</option>
      <option value="mixed">Mixed</option>
    </select>
    <select id="f-model" class="filter" aria-label="Filter by model tier">
      <option value="">Any model tier</option>
      <option value="cheap">Cheaper is fine</option>
      <option value="escalate">Start cheap, escalate</option>
      <option value="top-tier">Top-tier</option>
    </select>
    <label class="toggle"><input type="checkbox" id="f-starter" aria-label="Starter set only"> Starter set only</label>
  </div>
  <p id="count" class="lib-count" role="status" aria-live="polite" aria-atomic="true"></p>
  <div id="results" class="pcard-grid"></div>
  <p id="empty" class="empty" hidden>No prompts match. Clear a filter.</p>
</section>
"""
    return page("Library · prompt-os", body, "",
                desc=f"Searchable library of {CORPUS_PROMPT_COUNT} agent-loop prompts.",
                path="library.html",
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
                     "independent verifier, multi-armed stop — plus 11 principles and the antipatterns.",
                path="anatomy.html")


# ---- Family page ------------------------------------------------------------

def render_family(key: str, title: str, prompts: list[dict]) -> str:
    prefix = "../"
    fam = [p for p in prompts if p["family_key"] == key]
    cards = "".join(
        f'<a class="pcard" href="{prefix}prompt/{p["id"]}.html">'
        f'{card_title_html(p, num=True)}'
        f'<span class="pcard-when"{lang_attr(p["when"])}>{html.escape(p["when"][:140])}…</span>'
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
                desc=f"{len(fam)} {title} loop prompts.",
                path=f"family/{key}.html")


# ---- Glossary + Families index ---------------------------------------------

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# Every term below is used somewhere in the prompt corpus. Definitions are authored
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
  in the {CORPUS_PROMPT_COUNT} prompts — coloured dots map to the <a href="anatomy.html">loop anatomy</a>.</p>
  {"".join(secs)}
</section>
"""
    return page("Glossary · prompt-os", body, "",
                desc="A glossary of agent-loop and prompt-engineering terms — frozen goal, "
                     "independent verifier, multi-armed stop, Goodhart, ratchet, saturation, and more.",
                path="glossary.html")


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
  <h1 class="section-h">The {len(FAMILIES)} loop families</h1>
  <p class="section-sub">Every family is the same meta-shape — frozen goal → one action → independent
  verifier → multi-armed stop — specialized to a kind of work. The original families have 8 prompts each;
  newer ones (image generation, RAG, browser agents) are still growing.</p>
  <div class="fam-lg-grid">{cards}</div>
</section>
"""
    return page("Families · prompt-os", body, "",
                desc=f"The {len(FAMILIES)} agent-loop families in prompt-os, from build/verify and debugging "
                     "to RAG, browser agents, SQL analytics, tool use, memory, extraction, and video generation.",
                path="families.html")


# ----------------------------------------------------------------------------
# CSS + JS
# ----------------------------------------------------------------------------

# Stylesheet and client script live as real files so they can be linted, tested and
# diffed as CSS/JS. They are read at build time; the site stays dependency-free.
CSS = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
JS = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

def build():
    global ASSET_VER, CORPUS_PROMPT_COUNT
    # Inject the deterministic engine's rule tables into app.js so /lab & /compare
    # analyze arbitrary pasted text with the SAME rules as the Python build (one
    # source of truth). Done before hashing so cache-busting covers the rules.
    js_final = JS.replace("/*__RULES__*/",
                          "window.PROMPTOS_RULES=" + json_for_script(analysis_rules()) + ";")
    ASSET_VER = hashlib.md5((CSS + js_final).encode("utf-8")).hexdigest()[:8]

    prompts: list[dict] = []
    for key, _ in FAMILIES:
        prompts.extend(parse_family(key))

    # mark starter-set membership: exact match, or the starter's English title nested
    # inside a '中文(English)' prompt title (e.g. 'Fan-Out Research Synthesis').
    problems: list[str] = []   # fatal: corrupt corpus or output
    warnings: list[str] = []   # non-fatal: degraded but correct
    starter_titles = [t.lower() for t in parse_starter_titles()]
    matched_starters: set[str] = set()
    for p in prompts:
        tl = p["title"].lower()
        for st in starter_titles:
            if st == tl or st in tl:
                p["starter"] = True
                matched_starters.add(st)
    # A starter entry that matches no prompt means the curated index has drifted from
    # the corpus. This used to vanish silently, shrinking the starter set unnoticed.
    unresolved = [st for st in starter_titles if st not in matched_starters]
    if unresolved:
        problems.append(f"{len(unresolved)} starter-set titles match no prompt: {unresolved[:5]}")

    principles = parse_principles()

    # sanity: every declared family must contribute prompts (count grows as the corpus does)
    n = len(prompts)
    CORPUS_PROMPT_COUNT = n
    empty_fams = [k for k, _ in FAMILIES if not any(p["family_key"] == k for p in prompts)]
    if empty_fams:
        problems.append(f"families with no parsed prompts: {empty_fams}")
    missing_desc = [k for k, _ in FAMILIES if not FAMILY_DESC.get(k)]
    if missing_desc:
        # Non-fatal by design: family_desc() has a real fallback, and auto-discovery
        # ("drop a file, get a family") must not be blocked by a missing curated line.
        warnings.append(f"families using the generic fallback description: {missing_desc}")
    missing = [p["id"] for p in prompts if not p["prompt_text"]]
    if missing:
        problems.append(f"{len(missing)} prompts have empty prompt_text: {missing[:5]}")
    no_arms = [p["id"] for p in prompts if set(p["stop_arms"]) != set(STOP_ARM_NAMES)]
    if no_arms:
        problems.append(f"{len(no_arms)} prompts missing a stop arm: {no_arms[:5]}")
    starters = sum(1 for p in prompts if p["starter"])

    # analysis (deterministic)
    stats = corpus_stats(prompts)
    stats["generated_pages"] = 14 + len(prompts) + len(FAMILIES) + len(PATTERN_META) + len(AUTOMATIONS)
    related = build_related(prompts)
    # optional authored pattern reference docs (produced by the pattern workflow); seed
    # blurbs are used when absent, so the site is complete with or without them.
    docs_path = ROOT / "pattern_docs.json"
    pat_docs = json.loads(docs_path.read_text(encoding="utf-8")) if docs_path.exists() else {}
    auto_path = ROOT / "automation_docs.json"
    auto_docs = json.loads(auto_path.read_text(encoding="utf-8")) if auto_path.exists() else {}

    # FIX: build into a staging directory and swap only on success. Previously this
    # rmtree'd the live output first, so any exception mid-build left a partial site
    # that was indistinguishable from a complete one.
    global SITE
    final_site = SITE
    staging = final_site.parent / (final_site.name + ".staging")
    shutil.rmtree(staging, ignore_errors=True)
    SITE = staging
    (SITE / "prompt").mkdir(parents=True)
    (SITE / "family").mkdir(parents=True)
    (SITE / "pattern").mkdir(parents=True)
    (SITE / "automation").mkdir(parents=True)
    (SITE / "data").mkdir(parents=True)
    (SITE / "assets").mkdir(parents=True)

    (SITE / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (SITE / "assets" / "app.js").write_text(js_final, encoding="utf-8")
    # static social-preview image (committed source asset; used by og:image/twitter:image)
    og_src = ROOT / "assets" / "og.png"
    if og_src.exists():
        shutil.copy(og_src, SITE / "assets" / "og.png")
    else:
        print("  ! note: assets/og.png missing — social preview image will 404 until generated")

    # JSON search index (trim prompt_text to keep it lean but searchable)
    index = [{
        "id": p["id"], "title": p["display_title"], "alt": p["alt_title"],
        "full_title": p["title"], "when": p["when"],
        "family_key": p["family_key"], "family_title": p["family_title"],
        "verifier_type": p["verifier_type"], "model_hint": p["model_hint"],
        "model": p["model"],  # full routing note — lets /lab & /compare match detail-page classification exactly
        "starter": p["starter"],
        "patterns": [PATTERN_NAME[k] for k, _n, _r, _b in PATTERN_META if k in detect_patterns(p)],
        "prompt_text": p["prompt_text"],
    } for p in prompts]
    (SITE / "data" / "prompts.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    (SITE / "index.html").write_text(render_home(prompts, principles, stats), encoding="utf-8")
    (SITE / "library.html").write_text(render_library(), encoding="utf-8")
    (SITE / "anatomy.html").write_text(render_anatomy_page(principles, prompts), encoding="utf-8")
    (SITE / "families.html").write_text(render_families_index(prompts), encoding="utf-8")
    (SITE / "glossary.html").write_text(render_glossary(), encoding="utf-8")
    (SITE / "patterns.html").write_text(render_patterns_index(stats, pat_docs), encoding="utf-8")
    (SITE / "graph.html").write_text(render_graph(prompts, related), encoding="utf-8")
    (SITE / "find.html").write_text(render_find(), encoding="utf-8")
    (SITE / "lab.html").write_text(render_lab(), encoding="utf-8")
    (SITE / "compare.html").write_text(render_compare(), encoding="utf-8")
    (SITE / "learn.html").write_text(render_learn(prompts, principles), encoding="utf-8")
    (SITE / "evolve.html").write_text(render_evolution(), encoding="utf-8")
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

    sitemap_urls = write_sitemap_and_robots()
    # Count what was actually written rather than re-deriving it from a hand-summed
    # constant that drifts whenever a top-level page is added.
    total_pages = len(list(SITE.rglob("*.html")))
    if sitemap_urls != total_pages:
        problems.append(f"sitemap URL count {sitemap_urls} != generated page count {total_pages}")

    for w in warnings:
        print(f"  ! note: {w}")
    if problems:
        shutil.rmtree(staging, ignore_errors=True)
        SITE = final_site
        raise SystemExit("BUILD FAILED — corpus/output integrity:\n  - " + "\n  - ".join(problems))

    # atomic-ish swap: the live directory is only removed once staging is complete
    if final_site.exists():
        shutil.rmtree(final_site)
    staging.rename(final_site)
    SITE = final_site

    print(f"  parsed {n} prompts across {len(FAMILIES)} families ({starters} in starter set)")
    print(f"  wrote {total_pages} HTML pages + prompts.json + sitemap.xml + robots.txt + style.css + app.js -> {SITE.relative_to(ROOT)}/")
    print(f"  base url: {BASE_URL}")
    print(f"  open: {SITE / 'index.html'}")


if __name__ == "__main__":
    build()
