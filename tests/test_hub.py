"""Day 7: end-to-end coverage for the documentation hub (``render/hub.py``)
and doc-switcher cross-links, mirroring exactly what ``cli.py``'s
``_write_bundle``/``_write_hub`` do for a real multi-document job — but
against the real Corporate Spend fixture, whose original .pbip isn't in
this repo (only its previously-generated ``model.json`` is), so this can't
go through ``cli.main`` directly (that needs a source project path).
``tests/test_cli.py::test_all_html_creates_hub_and_doc_switcher_links``
already covers the CLI's own file-writing path on SampleSales; this module
is the "regenerate all four docs + hub" proof against the real fixture
that motivated the P0-P2/I1-I6 defect fixes.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pbicompass.agents.generators import DOCUMENT_TYPES
from pbicompass.render import registry
from pbicompass.render._shared import format_timestamp
from pbicompass.render.hub import doc_switcher_links, hub_stats, render_hub
from pbicompass.schemas.model import SemanticModel

CS_FIXTURE = Path(__file__).parent / "fixtures" / "CorporateSpend" / "model.json"


def _cs_model() -> SemanticModel:
    return SemanticModel.from_json(CS_FIXTURE.read_text(encoding="utf-8"))


class HubAndDocSwitcherTest(unittest.TestCase):
    """Builds the real 4-doc + hub bundle the way the CLI's ``--bundle``
    path does (``cli.py::_write_bundle``), then asserts every cross-link
    resolves — the hub links to each doc, and each doc's sidebar links
    back to its siblings and the hub."""

    @classmethod
    def setUpClass(cls):
        cls.model = _cs_model()
        cls.document_types = list(DOCUMENT_TYPES)  # ["technical", "audit", "executive", "user-guide"]
        cls.docs = {dtype: DOCUMENT_TYPES[dtype].generate(cls.model) for dtype in cls.document_types}
        cls.html_filenames = {d: f"{d}.html" for d in cls.document_types}

        cls.rendered_html = {}
        for dtype, doc in cls.docs.items():
            renderers = registry.RENDERERS[dtype]
            doc_links = doc_switcher_links(cls.document_types, dtype, cls.html_filenames, "index.html")
            cls.rendered_html[dtype] = renderers["html"](
                doc, doc_links=doc_links, sibling_hrefs=cls.html_filenames,
            )

        entries = [
            {"type": dtype, "href": cls.html_filenames[dtype], "stats": hub_stats(dtype, doc)}
            for dtype, doc in cls.docs.items()
        ]
        audit_doc = cls.docs["audit"]
        cls.health_score = {"overall": audit_doc.health.overall, "band": audit_doc.health.band}
        cls.hub_html = render_hub(
            entries, report_name=cls.model.report_name,
            generated_at=format_timestamp(cls.model.meta.generated_at),
            health_score=cls.health_score,
        )

    def test_all_four_docs_render_non_trivially(self):
        for dtype, html in self.rendered_html.items():
            self.assertGreater(len(html), 1000, f"{dtype} rendered suspiciously small")

    def test_hub_links_to_every_doc(self):
        for dtype in self.document_types:
            self.assertIn(self.html_filenames[dtype], self.hub_html, f"hub is missing a card for {dtype!r}")

    def test_hub_shows_the_real_computed_health_score(self):
        self.assertIn(f"{self.health_score['overall']}/100", self.hub_html)
        self.assertIn(self.health_score["band"], self.hub_html)

    def test_hub_report_name_matches_the_model(self):
        self.assertIn("Corporate Spend", self.hub_html)

    def test_every_doc_links_back_to_the_hub_and_its_siblings(self):
        for dtype, html in self.rendered_html.items():
            self.assertIn("index.html", html, f"{dtype} has no link back to the hub")
            for other in self.document_types:
                if other == dtype:
                    continue
                self.assertIn(
                    self.html_filenames[other], html,
                    f"{dtype}'s doc-switcher is missing a link to sibling {other!r}",
                )

    def test_doc_switcher_never_links_to_its_own_document(self):
        for dtype, html in self.rendered_html.items():
            switcher = html.split('class="doc-switcher"')[1].split("</nav>")[0]
            self.assertNotIn(self.html_filenames[dtype], switcher)

    def test_hub_stats_reflect_the_real_fixture(self):
        # Corporate Spend: 11 tables (audited health score varies with the
        # rule set, so only the shape-stable stats are asserted directly).
        technical_stats = dict(hub_stats("technical", self.docs["technical"]))
        self.assertEqual(technical_stats["tables"], 11)
        user_guide_stats = dict(hub_stats("user-guide", self.docs["user-guide"]))
        self.assertEqual(user_guide_stats["pages"], len([p for p in self.model.pages if not p.is_hidden]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
