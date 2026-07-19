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


class A11yCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.heading_levels: list[int] = []
        self.h1_count = 0
        self.main_count = 0
        self.skip_links: list[str] = []
        self.navs: list[dict[str, str | None]] = []
        self.labels_for: set[str] = set()
        self.controls: list[tuple[str, dict[str, str | None]]] = []
        self.tabs: list[dict[str, str | None]] = []
        self.tabpanels: list[dict[str, str | None]] = []
        self.tablists: list[dict[str, str | None]] = []
        self.buttons: list[tuple[dict[str, str | None], str]] = []
        self._button_stack: list[tuple[dict[str, str | None], list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if "id" in attr_map and attr_map["id"]:
            self.ids.add(attr_map["id"])
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.heading_levels.append(int(tag[1]))
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.main_count += 1
        if tag == "a" and "skip" in (attr_map.get("class") or "").split():
            self.skip_links.append(attr_map.get("href") or "")
        if tag == "nav":
            self.navs.append(attr_map)
        if tag == "label" and attr_map.get("for"):
            self.labels_for.add(attr_map["for"] or "")
        if tag in ("input", "select", "textarea"):
            self.controls.append((tag, attr_map))
        if attr_map.get("role") == "tablist":
            self.tablists.append(attr_map)
        if attr_map.get("role") == "tab":
            self.tabs.append(attr_map)
        if attr_map.get("role") == "tabpanel":
            self.tabpanels.append(attr_map)
        if tag == "button":
            self._button_stack.append((attr_map, []))

    def handle_data(self, data: str) -> None:
        if self._button_stack:
            self._button_stack[-1][1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button_stack:
            attrs, parts = self._button_stack.pop()
            self.buttons.append((attrs, " ".join("".join(parts).split())))


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

    def test_generated_pages_have_basic_accessible_structure(self) -> None:
        for path in build_site.SITE.rglob("*.html"):
            parser = A11yCollector()
            parser.feed(path.read_text(encoding="utf-8"))
            with self.subTest(path=str(path.relative_to(build_site.ROOT))):
                self.assertEqual(1, parser.h1_count)
                self.assertEqual(1, parser.main_count)
                self.assertIn("main", parser.ids)
                self.assertIn("#main", parser.skip_links)
                self.assertTrue(parser.navs)
                self.assertTrue(any(nav.get("aria-label") for nav in parser.navs))
                jumps = [(a, b) for a, b in zip(parser.heading_levels, parser.heading_levels[1:]) if b > a + 1]
                self.assertEqual([], jumps)

    def test_interactive_controls_have_accessible_names(self) -> None:
        unnamed: list[tuple[str, str, dict[str, str | None]]] = []
        for path in build_site.SITE.rglob("*.html"):
            parser = A11yCollector()
            parser.feed(path.read_text(encoding="utf-8"))
            rel = str(path.relative_to(build_site.ROOT))
            for attrs, text in parser.buttons:
                if not (attrs.get("aria-label") or text):
                    unnamed.append((rel, "button", attrs))
            for tag, attrs in parser.controls:
                if attrs.get("type") == "hidden":
                    continue
                control_id = attrs.get("id")
                if not (attrs.get("aria-label") or attrs.get("aria-labelledby") or (control_id and control_id in parser.labels_for)):
                    unnamed.append((rel, tag, attrs))
        self.assertEqual([], unnamed)

    def test_tab_widgets_have_required_aria_relationships(self) -> None:
        for path in build_site.SITE.rglob("*.html"):
            parser = A11yCollector()
            parser.feed(path.read_text(encoding="utf-8"))
            if not parser.tablists and not parser.tabs and not parser.tabpanels:
                continue
            with self.subTest(path=str(path.relative_to(build_site.ROOT))):
                self.assertTrue(parser.tablists)
                self.assertTrue(parser.tabs)
                self.assertTrue(parser.tabpanels)
                selected = [tab for tab in parser.tabs if tab.get("aria-selected") == "true"]
                self.assertEqual(1, len(selected))
                for tab in parser.tabs:
                    self.assertIn(tab.get("aria-selected"), {"true", "false"})
                    self.assertIn(tab.get("aria-controls"), parser.ids)
                for panel in parser.tabpanels:
                    self.assertIn(panel.get("aria-labelledby"), parser.ids)

    def test_dynamic_widget_a11y_hooks_are_emitted(self) -> None:
        js = (build_site.SITE / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("aria-pressed", js)
        self.assertIn("aria-current", js)
        self.assertIn("e.target !== root", js)
        self.assertIn("lastGraphNode", js)
        self.assertIn("el.setAttribute('tabindex', off ? '-1' : '0')", js)

        loops = (build_site.SITE / "loops.html").read_text(encoding="utf-8")
        self.assertIn('role="region" aria-label="Interactive loop visualizer"', loops)
        self.assertIn('aria-live="polite" aria-atomic="true"', loops)

        graph = (build_site.SITE / "graph.html").read_text(encoding="utf-8")
        self.assertIn('id="graphWrap" role="region"', graph)
        self.assertIn('Filter graph by family', graph)

        library = (build_site.SITE / "library.html").read_text(encoding="utf-8")
        self.assertIn('aria-label="Search prompts"', library)
        self.assertIn('id="count" class="lib-count" role="status"', library)


if __name__ == "__main__":
    unittest.main()
