from __future__ import annotations

import copy
import unittest
from pathlib import Path

from pbicompass.agents import generate_document
from pbicompass.agents.generators import (
    AuditReportGenerator, BusinessGuideGenerator, ExecutiveSummaryGenerator,
)
from pbicompass.agents.output_gate import (
    OutputQualityError, canonicalize_bundle, validate_bundle,
)
from pbicompass.parsers import detect_and_parse


FIXTURE = Path(__file__).parent / "fixtures" / "SampleSales" / "SampleSales.pbip"


class OutputGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = detect_and_parse(FIXTURE)
        cls.docs = {
            "technical": generate_document(cls.model),
            "audit": AuditReportGenerator.generate(cls.model),
            "executive": ExecutiveSummaryGenerator.generate(cls.model),
            "user-guide": BusinessGuideGenerator.generate(cls.model),
        }

    def test_valid_full_bundle_passes(self):
        rendered = validate_bundle(copy.deepcopy(self.docs), self.model)
        self.assertEqual(set(rendered), set(self.docs))

    def test_canonicalizes_model_object_spelling(self):
        docs = copy.deepcopy(self.docs)
        expected = docs["technical"].measure_catalog.measures[0].name
        docs["technical"].measure_catalog.measures[0].name = expected.swapcase()
        canonicalize_bundle(docs, self.model)
        self.assertEqual(docs["technical"].measure_catalog.measures[0].name, expected)

    def test_blocks_raw_placeholder(self):
        docs = copy.deepcopy(self.docs)
        docs["executive"].purpose = "TODO replace this paragraph"
        with self.assertRaisesRegex(OutputQualityError, "PLACEHOLDER"):
            validate_bundle(docs, self.model)

    def test_blocks_cross_document_duplicate_paragraph(self):
        docs = copy.deepcopy(self.docs)
        docs["executive"].purpose = docs["technical"].executive_summary.core_purpose
        with self.assertRaisesRegex(OutputQualityError, "DEDUP"):
            validate_bundle(docs, self.model)

    def test_blocks_broken_internal_navigation(self):
        docs = copy.deepcopy(self.docs)
        page = docs["user-guide"].pages[0]
        page.wireframe_svg = '<svg><a href="#missing-object"><text>Broken</text></a></svg>'
        with self.assertRaisesRegex(OutputQualityError, "HTML-NAV"):
            validate_bundle(docs, self.model)


if __name__ == "__main__":
    unittest.main()
