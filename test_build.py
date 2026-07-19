#!/usr/bin/env python3
"""Regression self-checks for the dependency-free site generator."""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import build_site


EXPECTED_PROMPTS = 149
EXPECTED_FAMILIES = 23
EXPECTED_HTML_PAGES = 209


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        for name in ("href", "src"):
            value = attr_map.get(name)
            if value:
                self.refs.append(value)


class BuildSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_site.build()
        cls.prompts = []
        for key, _title in build_site.FAMILIES:
            cls.prompts.extend(build_site.parse_family(key))

    def test_corpus_parse_invariants(self) -> None:
        self.assertEqual(EXPECTED_FAMILIES, len(build_site.FAMILIES))
        self.assertEqual(EXPECTED_PROMPTS, len(self.prompts))

        for key, _title in build_site.FAMILIES:
            parsed = build_site.parse_family(key)
            self.assertGreater(len(parsed), 0, key)

        for prompt in self.prompts:
            with self.subTest(prompt=prompt["id"]):
                self.assertTrue(prompt["prompt_text"].strip())
                self.assertEqual(set(build_site.STOP_ARM_NAMES), set(prompt["stop_arms"]))
                self.assertTrue(all(v.strip() for v in prompt["stop_arms"].values()))

    def test_stop_arm_parser_ignores_arm_words_inside_descriptions(self) -> None:
        arms = build_site.parse_stop_arms(
            "SUCCESS: verified before BUDGET expires · "
            "BUDGET: cap reached · NO-PROGRESS: flat · BLOCKED: missing access"
        )
        self.assertEqual("verified before BUDGET expires", arms["SUCCESS"])
        self.assertEqual(set(build_site.STOP_ARM_NAMES), set(arms))

    def test_inline_script_json_is_html_safe(self) -> None:
        encoded = build_site.json_for_script({"x": "</script><!-- --> & \u2028"})
        self.assertNotIn("</script", encoded.lower())
        self.assertNotIn("<!--", encoded)
        self.assertNotIn("-->", encoded)
        self.assertIn("\\u003c/script\\u003e", encoded)

    def test_generated_output_integrity(self) -> None:
        html_files = sorted(build_site.SITE.rglob("*.html"))
        self.assertEqual(EXPECTED_HTML_PAGES, len(html_files))

        unresolved = (
            "{html.escape(", "{json.dumps(", "{prefix}", "{body}", "{extra_head}",
            "{ASSET_VER}", "{render_", "{stats[", "{p['", '{p["', "{demo[",
            "{principles[", "{CORPUS_PROMPT_COUNT}",
        )
        for path in html_files:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path.relative_to(build_site.ROOT))):
                for marker in unresolved:
                    self.assertNotIn(marker, text)
                self.assertIsNone(re.search(r"\bNone\b", text))
                for match in re.finditer(r"<script>window\.(?:GRAPH|LOOPVIZ)\s*=\s*(.*?);</script>", text, re.S):
                    payload = match.group(1)
                    self.assertNotIn("</script", payload.lower())
                    self.assertNotIn("<!--", payload)
                    self.assertNotIn("-->", payload)

    def test_internal_links_resolve(self) -> None:
        site_root = build_site.SITE.resolve()
        broken: list[tuple[Path, str]] = []
        for path in build_site.SITE.rglob("*.html"):
            parser = LinkCollector()
            parser.feed(path.read_text(encoding="utf-8"))
            for ref in parser.refs:
                if ref.startswith(("#", "http:", "https:", "mailto:", "tel:", "data:", "javascript:")):
                    continue
                link_path = urlsplit(ref).path
                if not link_path:
                    continue
                target = (path.parent / link_path).resolve()
                try:
                    target.relative_to(site_root)
                except ValueError:
                    broken.append((path, ref))
                    continue
                if not target.exists():
                    broken.append((path, ref))
        self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
