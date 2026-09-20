#!/usr/bin/env python3
"""Raise corpus_baseline.json to the corpus's current size — a deliberate act.

The test suite asserts the corpus never SHRINKS. Growing it is expected and needs no
code edit; recording the new floor is a reviewed, explicit step.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_site  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "corpus_baseline.json"
data = json.loads(path.read_text())

prompts = [p for key, _ in build_site.FAMILIES for p in build_site.parse_family(key)]
before = dict(data)
data["min_prompts"] = len(prompts)
data["min_families"] = len(build_site.FAMILIES)
data["min_principles"] = len(build_site.parse_principles()["principles"])
path.write_text(json.dumps(data, indent=2) + "\n")
print(f"baseline: {before['min_prompts']}->{data['min_prompts']} prompts, "
      f"{before['min_families']}->{data['min_families']} families, "
      f"{before['min_principles']}->{data['min_principles']} principles")
