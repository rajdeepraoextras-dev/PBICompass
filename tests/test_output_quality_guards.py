"""Sprint 1 Day 5 (PRODUCTION_ROADMAP.md Sec 10.1): consolidated, end-to-end
output-quality guards.

Days 1-4 fixed D1/D2/D3/D4/D6 and each added unit/wiring-level regression
tests near the fix itself (test_sanitize.py, test_critic.py, test_grounding.py,
test_report_facts.py, test_generators.py, test_agents.py::AntiPuntGuardTest).
This module is the holistic complement the roadmap's Sec 10.1 asks for: it
renders the full, real SampleSales document set the way a customer would
receive it (all 4 document types, md + html) and asserts the defect patterns
are absent from the *actual rendered output*, not just from a hand-built
fixture exercising one code path. It is the permanent CI lock-in for the
Sprint 1 fixes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from pbicompass.agents import generate_document
from pbicompass.agents.generators import (
    AuditReportGenerator,
    BusinessGuideGenerator,
    ExecutiveSummaryGenerator,
)
from pbicompass.parsers import detect_and_parse
from pbicompass.render import (
    render_audit_html,
    render_audit_markdown,
    render_executive_html,
    render_executive_markdown,
    render_html,
    render_markdown,
    render_user_guide_html,
    render_user_guide_markdown,
)

FIXTURE = Path(__file__).parent / "fixtures" / "SampleSales" / "SampleSales.pbip"

# D2 - unambiguous artifacts of LLM meta-commentary/editing-directives that
# leaked into shipped prose. These substrings have no legitimate occurrence
# anywhere in a rendered doc (unlike bare "Remove"/"Add a", which are also
# the deterministic audit engine's own imperative fix-recommendation prose).
_D2_ARTIFACT_PATTERNS = [
    re.compile(r"glossary\[\d+\]"),
    re.compile(r"plain_definition"),
    re.compile(r"the duplicated entry"),
]

# D1 - audit-speak / internal-completeness-nag vocabulary banned from the
# executive doc specifically (roadmap's own done-when list).
_D1_BANNED_PHRASES = ["governance finding", "best practice", "% complete", "fields still need"]

# D4 - a bare field-parameter token. Lowercase, whole-word: the codebase's
# own legitimate English usage always capitalizes "Select" (e.g. "Select
# 'View as'" in the RLS test checklist), so a case-sensitive lowercase match
# does not false-positive on normal prose. The negative lookbehind excludes
# the CSS property "user-select" (Day 6's pan/zoom styling) — \b treats the
# hyphen as a non-word boundary, so "user-select" would otherwise match
# "select" as a bare "word" even though it's not a leaked field-parameter
# token at all.
_D4_FIELD_SELECTOR_RE = re.compile(r"(?<!-)\bselect1?\b")

_PUNT_PHRASE = "requires business confirmation"

_COLUMN_ROW_RE = re.compile(
    r'<tr id="column-[^"]+"><td>([^<]*)</td><td>([^<]*)</td><td>[^<]*</td><td>([^<]*)</td>'
)


def _relationship_columns(model) -> set[tuple[str, str]]:
    """(table, column) pairs that participate in at least one relationship -
    the D6 fix's whole point is that these must never render the punt phrase."""
    pairs: set[tuple[str, str]] = set()
    for rel in model.relationships:
        pairs.add((rel.from_table, rel.from_column))
        pairs.add((rel.to_table, rel.to_column))
    return pairs


class OutputQualityGuardsTest(unittest.TestCase):
    """One parse, one generate-per-type, every rendered surface scanned."""

    @classmethod
    def setUpClass(cls):
        cls.model = detect_and_parse(FIXTURE)
        cls.technical_doc = generate_document(cls.model)
        cls.audit_doc = AuditReportGenerator.generate(cls.model)
        cls.executive_doc = ExecutiveSummaryGenerator.generate(cls.model)
        cls.user_guide_doc = BusinessGuideGenerator.generate(cls.model)

        cls.rendered = {
            "technical.html": render_html(cls.technical_doc),
            "technical.md": render_markdown(cls.technical_doc),
            "audit.html": render_audit_html(cls.audit_doc),
            "audit.md": render_audit_markdown(cls.audit_doc),
            "executive.html": render_executive_html(cls.executive_doc),
            "executive.md": render_executive_markdown(cls.executive_doc),
            "user_guide.html": render_user_guide_html(cls.user_guide_doc),
            "user_guide.md": render_user_guide_markdown(cls.user_guide_doc),
        }

    # ---- D1: exec doc reads for a business owner, not an auditor --------

    def test_d1_no_audit_speak_in_executive_doc(self):
        for name in ("executive.html", "executive.md"):
            text = self.rendered[name]
            for phrase in _D1_BANNED_PHRASES:
                self.assertNotIn(
                    phrase.lower(), text.lower(),
                    f"D1 regression: {phrase!r} found in {name}",
                )

    # ---- D2: no LLM meta-commentary/editing-directives in any doc -------

    def test_d2_no_meta_commentary_artifacts_in_any_doc(self):
        for name, text in self.rendered.items():
            for pattern in _D2_ARTIFACT_PATTERNS:
                match = pattern.search(text)
                self.assertIsNone(
                    match, f"D2 regression: {pattern.pattern!r} found in {name} ({match})"
                )

    # ---- D3: grounding never splices mid-sentence -------------------------

    def test_d3_no_mid_sentence_splice_artifacts_in_any_doc(self):
        for name, text in self.rendered.items():
            self.assertNotIn(".,", text, f"D3 regression: '.,' splice found in {name}")
            self.assertNotIn(
                f"{_PUNT_PHRASE}..", text,
                f"D3 regression: doubled terminal punctuation found in {name}",
            )

    # ---- D4: no bare select/select1 field-selector leaks -------------------

    def test_d4_no_bare_field_selector_tokens_in_any_doc(self):
        for name, text in self.rendered.items():
            match = _D4_FIELD_SELECTOR_RE.search(text)
            self.assertIsNone(match, f"D4 regression: bare field-selector token in {name} ({match})")

    # ---- D6: punt phrase bounded, never on a relationship-participating col

    def test_d6_punt_phrase_bounded_and_never_on_relationship_column(self):
        rel_columns = _relationship_columns(self.model)

        for name in ("technical.html",):
            text = self.rendered[name]
            total = text.count(_PUNT_PHRASE)
            self.assertLessEqual(
                total, 2,
                f"D6 regression: '{_PUNT_PHRASE}' count ({total}) is no longer bounded in {name} "
                "- the anti-punt merge policy may have regressed.",
            )

            for table, column, description in _COLUMN_ROW_RE.findall(text):
                if _PUNT_PHRASE not in description:
                    continue
                self.assertNotIn(
                    (table, column), rel_columns,
                    f"D6 regression: relationship-participating column {table}.{column} "
                    f"rendered the punt phrase instead of its deterministic join-key description.",
                )

    # ---- Sanity: the guards above aren't vacuously passing on empty docs --

    def test_rendered_docs_are_non_trivial(self):
        for name, text in self.rendered.items():
            self.assertGreater(len(text), 500, f"{name} rendered suspiciously small ({len(text)} chars)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
