#!/usr/bin/env python3
"""Regression self-checks for the dependency-free site generator."""
from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import build_site


EXPECTED_PROMPTS = 158
EXPECTED_FAMILIES = 26
EXPECTED_HTML_PAGES = 225  # 14 top-level pages + 158 prompt + 26 family + 15 pattern + 12 automation
ANATOMY_SHORT_ALLOWLIST = {"orchestration-harness-8"}


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


class SeoCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.charset = ""
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.body_refs: list[tuple[str, str]] = []
        self._in_title = False
        self._in_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "html":
            self.html_lang = attr_map.get("lang") or ""
        elif tag == "body":
            self._in_body = True
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            if attr_map.get("charset"):
                self.charset = attr_map.get("charset") or ""
            key = attr_map.get("name") or attr_map.get("property")
            if key:
                self.meta[key] = attr_map.get("content") or ""
        elif tag == "link":
            rel = attr_map.get("rel")
            if rel:
                self.links[rel] = attr_map.get("href") or ""

        if self._in_body:
            for attr in ("href", "src"):
                if attr_map.get(attr):
                    self.body_refs.append((tag, attr_map[attr] or ""))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "body":
            self._in_body = False


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

        missing_desc = [key for key, _title in build_site.FAMILIES if not build_site.FAMILY_DESC.get(key)]
        self.assertEqual([], missing_desc)

        for prompt in self.prompts:
            with self.subTest(prompt=prompt["id"]):
                self.assertTrue(prompt["prompt_text"].strip())
                self.assertEqual(set(build_site.STOP_ARM_NAMES), set(prompt["stop_arms"]))
                self.assertTrue(all(v.strip() for v in prompt["stop_arms"].values()))

    def test_no_authoring_metadata_leaks_into_corpus(self) -> None:
        leaked: list[tuple[str, str]] = []
        patterns = ("Task: author", "(subagent)", "scenario =", "in the library's style")
        for path in build_site.LOOPS.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern in text:
                    leaked.append((path.name, pattern))
        self.assertEqual([], leaked)

    def test_explicit_verifier_labels_classify(self) -> None:
        explicit = [
            prompt for prompt in self.prompts
            if re.search(r"\bVERIFIER\s*:", prompt["prompt_text"], re.I)
        ]
        self.assertGreater(len(explicit), 0)
        unspecified = [prompt["id"] for prompt in explicit if prompt["verifier_type"] == "unspecified"]
        self.assertEqual([], unspecified)

    def test_prompt_anatomy_segmentation_has_multiple_roles(self) -> None:
        weak: list[tuple[str, list[str]]] = []
        for prompt in self.prompts:
            if prompt["id"] in ANATOMY_SHORT_ALLOWLIST:
                continue
            roles = sorted({role for role, _text in build_site.segment_anatomy(prompt["prompt_text"])})
            if len(roles) < 3:
                weak.append((prompt["id"], roles))
        self.assertEqual([], weak)

    def test_stop_arm_parser_ignores_arm_words_inside_descriptions(self) -> None:
        arms = build_site.parse_stop_arms(
            "SUCCESS: verified before BUDGET expires · "
            "BUDGET: cap reached · NO-PROGRESS: flat · BLOCKED: missing access"
        )
        self.assertEqual("verified before BUDGET expires", arms["SUCCESS"])
        self.assertEqual(set(build_site.STOP_ARM_NAMES), set(arms))

    def test_lab_and_compare_wiring(self) -> None:
        # analysis rules injected into app.js (single source of truth), placeholder gone
        js = (build_site.SITE / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("/*__RULES__*/", js)
        self.assertIn("window.PROMPTOS_RULES=", js)
        for kw in build_site.MECH_KEYWORDS[:3]:
            self.assertIn(kw, js)  # rule tables actually serialized
        # /lab and /compare exist with their JS root hooks
        lab = (build_site.SITE / "lab.html").read_text(encoding="utf-8")
        self.assertIn('id="labInput"', lab)
        cmp_ = (build_site.SITE / "compare.html").read_text(encoding="utf-8")
        self.assertIn('id="cmpSelA"', cmp_)
        self.assertIn('id="cmpSelB"', cmp_)
        # engine mirrors the module's verifier keyword source, not a hardcoded copy
        self.assertIn("R.mechKw", js)
        self.assertIn("R.judgeKw", js)

    def test_learn_course_is_wired_and_grounded(self) -> None:
        learn = (build_site.SITE / "learn.html").read_text(encoding="utf-8")
        # one lesson + quiz per module, each with a valid answer index
        self.assertEqual(len(build_site.LEARN_MODULES), learn.count('class="lesson"'))
        correct_markers = re.findall(r'class="quiz" data-correct="(\d+)"', learn)
        self.assertEqual(len(build_site.LEARN_MODULES), len(correct_markers))
        for module, marker in zip(build_site.LEARN_MODULES, correct_markers):
            self.assertLess(int(marker), len(module["quiz"]["options"]))  # answer index in range
        # grounded: at least one lesson quotes a real principle body verbatim
        principles = build_site.parse_principles()
        bodies = [p["body"] for p in principles["principles"]]
        self.assertTrue(any(build_site.html.escape(b[:60]) in learn for b in bodies),
                        "learn page should quote real principle text, not fabricated prose")
        # quiz interactivity + localStorage wired in app.js
        js = (build_site.SITE / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("promptos_learn_v1", js)
        self.assertIn(".learn-page", js)

    def test_analysis_rules_cover_engine(self) -> None:
        rules = build_site.analysis_rules()
        self.assertEqual(list(build_site.MECH_KEYWORDS), rules["mechKw"])
        self.assertEqual(list(build_site.JUDGE_KEYWORDS), rules["judgeKw"])
        self.assertEqual([k for k, *_ in build_site.PATTERN_META],
                         [row[0] for row in rules["patternMeta"]])
        self.assertEqual(list(build_site.STOP_ARM_NAMES), rules["stopArms"])

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

    def test_view_transition_css_is_progressive_and_motion_safe(self) -> None:
        css = (build_site.SITE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIn("@view-transition{navigation:auto}", css)
        self.assertIn("::view-transition-old(root)", css)
        self.assertIn("::view-transition-new(root)", css)
        self.assertIn("view-transition-name:site-header", css)
        self.assertIn("@media (prefers-reduced-motion:reduce)", css)
        self.assertIn("::view-transition-group(*)", css)
        self.assertNotIn("transition:all", css)

    def test_header_nav_can_wrap_before_mobile_widths(self) -> None:
        css = (build_site.SITE / "assets" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".site-head nav{display:flex;gap:22px;flex-wrap:wrap}", css)
        self.assertIn("@media (max-width:820px)", css)
        self.assertIn(".head-inner{height:auto;min-height:60px;flex-wrap:wrap", css)
        self.assertIn(".brand{flex:1 1 100%}", css)

    def test_generated_pages_have_share_metadata(self) -> None:
        descriptions: list[str] = []
        for path in build_site.SITE.rglob("*.html"):
            parser = SeoCollector()
            parser.feed(path.read_text(encoding="utf-8"))
            rel = path.relative_to(build_site.SITE).as_posix()
            expected_url = build_site.absolute_url(rel)
            desc = parser.meta.get("description", "").strip()
            descriptions.append(desc)
            with self.subTest(path=rel):
                self.assertEqual("en", parser.html_lang)
                self.assertEqual("utf-8", parser.charset.lower())
                self.assertEqual("width=device-width, initial-scale=1", parser.meta.get("viewport"))
                self.assertGreater(len(desc), 20)
                self.assertEqual(expected_url, parser.links.get("canonical"))
                self.assertEqual(parser.title.strip(), parser.meta.get("og:title"))
                self.assertEqual(desc, parser.meta.get("og:description"))
                self.assertEqual("website", parser.meta.get("og:type"))
                self.assertEqual(expected_url, parser.meta.get("og:url"))
                self.assertEqual("prompt-os", parser.meta.get("og:site_name"))
                self.assertEqual("summary", parser.meta.get("twitter:card"))

                absolute_body_refs = [
                    ref for _tag, ref in parser.body_refs
                    if ref.startswith(build_site.BASE_URL)
                ]
                self.assertEqual([], absolute_body_refs)

        duplicates = [desc for desc, count in Counter(descriptions).items() if count > 1]
        self.assertEqual([], duplicates)

    def test_sitemap_and_robots(self) -> None:
        html_files = sorted(build_site.SITE.rglob("*.html"))
        expected_urls = {
            build_site.absolute_url(path.relative_to(build_site.SITE).as_posix())
            for path in html_files
        }

        sitemap_path = build_site.SITE / "sitemap.xml"
        self.assertTrue(sitemap_path.exists())
        root = ET.parse(sitemap_path).getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = {node.text for node in root.findall(".//sm:loc", namespace)}
        self.assertEqual(len(html_files), len(urls))
        self.assertEqual(expected_urls, urls)

        robots = (build_site.SITE / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {build_site.absolute_url('sitemap.xml')}", robots)


if __name__ == "__main__":
    unittest.main()
