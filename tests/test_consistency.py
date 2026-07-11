"""Tests for the cross-artifact consistency pass (Day 2): ``agents/consistency.py``'s
deterministic fixed-vocabulary checker, LLM-routed checker, and end-to-end
wiring into the document generators."""

from __future__ import annotations

import unittest
from pathlib import Path

from pbicompass.agents.consistency import (
    AuditVerdicts,
    apply_consistency_pass,
    build_audit_verdicts,
    check_consistency,
    check_deterministic_consistency,
)
from pbicompass.agents.critic import apply_results
from pbicompass.agents.generators import (
    AuditReportGenerator,
    ExecutiveSummaryGenerator,
    TechnicalDocumentationGenerator,
)
from pbicompass.parsers import detect_and_parse

FIXTURE = Path(__file__).parent / "fixtures" / "SampleSales" / "SampleSales.pbip"


def _model():
    return detect_and_parse(FIXTURE)


def _verdicts(**overrides) -> AuditVerdicts:
    base = dict(
        schema_shape="a snowflake schema (dimensions relate to other dimensions)",
        is_star_schema=False,
        fact_count=1,
        dim_count=4,
        rls_role_count=2,
        refresh_configured=True,
        description_coverage_pct=40,
    )
    base.update(overrides)
    return AuditVerdicts(**base)


class BuildAuditVerdictsTest(unittest.TestCase):
    def test_verdicts_reflect_the_audit_documents_own_computation(self):
        model = _model()
        audit_doc = AuditReportGenerator.generate(model)
        verdicts = build_audit_verdicts(model, audit_doc)

        from pbicompass.agents.deterministic import schema_shape
        shape, facts, dims = schema_shape(model)
        self.assertEqual(verdicts.schema_shape, shape)
        self.assertEqual(verdicts.fact_count, len(facts))
        self.assertEqual(verdicts.dim_count, len(dims))
        self.assertEqual(verdicts.rls_role_count, len(model.roles))
        star_check = next(c for c in audit_doc.best_practices if c.id == "star_schema")
        self.assertEqual(verdicts.is_star_schema, star_check.passed)


class CheckDeterministicConsistencyTest(unittest.TestCase):
    def test_false_star_schema_claim_is_corrected(self):
        verdicts = _verdicts(is_star_schema=False, schema_shape="a snowflake schema (dimensions relate to other dimensions)")
        results = check_deterministic_consistency(
            [("a", "This report is built on a well-structured star schema for fast analysis.")],
            verdicts,
        )
        self.assertIn("a", results)
        self.assertNotIn("star schema", results["a"])
        self.assertIn("snowflake schema", results["a"])

    def test_true_star_schema_claim_is_left_untouched(self):
        verdicts = _verdicts(is_star_schema=True, schema_shape="a star schema centred on the 'Sales' fact table")
        results = check_deterministic_consistency(
            [("a", "This report is built on a star schema for fast analysis.")], verdicts,
        )
        self.assertEqual(results, {})

    def test_hedged_not_star_schema_claim_is_left_untouched(self):
        # Already correctly says it's not a star schema — nothing to fix.
        verdicts = _verdicts(is_star_schema=False)
        results = check_deterministic_consistency(
            [("a", "This model is not a star schema; it uses a layered dimension design.")], verdicts,
        )
        self.assertEqual(results, {})

    def test_no_rls_claim_is_corrected_when_roles_exist(self):
        verdicts = _verdicts(rls_role_count=3)
        results = check_deterministic_consistency(
            [("a", "No row-level security is configured for this report.")], verdicts,
        )
        self.assertIn("3 row-level security roles", results["a"])

    def test_wrong_rls_count_is_corrected(self):
        verdicts = _verdicts(rls_role_count=2)
        results = check_deterministic_consistency(
            [("a", "This model defines 5 RLS roles for regional access control.")], verdicts,
        )
        self.assertIn("2 RLS roles", results["a"])
        self.assertNotIn("5 RLS roles", results["a"])

    def test_correct_rls_count_is_left_untouched(self):
        verdicts = _verdicts(rls_role_count=2)
        results = check_deterministic_consistency(
            [("a", "This model defines 2 RLS roles for regional access control.")], verdicts,
        )
        self.assertEqual(results, {})

    def test_refresh_not_configured_claim_is_corrected_when_it_is(self):
        verdicts = _verdicts(refresh_configured=True)
        results = check_deterministic_consistency(
            [("a", "The refresh schedule is not configured for this report.")], verdicts,
        )
        self.assertIn("refresh is configured", results["a"])

    def test_wrong_fact_table_count_is_corrected(self):
        verdicts = _verdicts(fact_count=1)
        results = check_deterministic_consistency(
            [("a", "The model spans 3 fact tables feeding every dashboard.")], verdicts,
        )
        self.assertIn("1 fact table", results["a"])
        self.assertNotIn("3 fact tables", results["a"])

    def test_wrong_dimension_table_count_is_corrected(self):
        verdicts = _verdicts(dim_count=4)
        results = check_deterministic_consistency(
            [("a", "The model includes 9 dimension tables for slicing.")], verdicts,
        )
        self.assertIn("4 dimension tables", results["a"])

    def test_full_coverage_claim_is_corrected_when_partial(self):
        verdicts = _verdicts(description_coverage_pct=40)
        results = check_deterministic_consistency(
            [("a", "Every measure has a description, making the model self-documenting.")], verdicts,
        )
        self.assertIn("40%", results["a"])

    def test_full_coverage_claim_left_untouched_when_actually_full(self):
        verdicts = _verdicts(description_coverage_pct=100)
        results = check_deterministic_consistency(
            [("a", "All measures are documented for easy onboarding.")], verdicts,
        )
        self.assertEqual(results, {})

    def test_multiple_contradictions_in_one_field_all_corrected(self):
        verdicts = _verdicts(is_star_schema=False, rls_role_count=3,
                              schema_shape="a snowflake schema (dimensions relate to other dimensions)")
        results = check_deterministic_consistency(
            [("a", "This star schema model has no row-level security.")], verdicts,
        )
        self.assertIn("snowflake schema", results["a"])
        self.assertNotIn("no row-level security", results["a"])
        self.assertIn("3 row-level security roles", results["a"])

    def test_empty_text_is_skipped(self):
        results = check_deterministic_consistency([("a", "")], _verdicts())
        self.assertEqual(results, {})

    def test_clean_prose_with_no_claims_is_untouched(self):
        verdicts = _verdicts()
        results = check_deterministic_consistency(
            [("a", "This report tracks quarterly sales performance across regions.")], verdicts,
        )
        self.assertEqual(results, {})


class FakeConsistencyClient:
    def __init__(self, contradictions: list[dict]):
        self.contradictions = contradictions
        self.calls = 0

    def complete_json(self, system: str, user: str, schema: dict, *, effort: str | None = None) -> dict:
        self.calls += 1
        return {"contradictions": self.contradictions}


class ApplyConsistencyPassTest(unittest.TestCase):
    def test_offline_is_a_noop(self):
        results = apply_consistency_pass([("a", "Some claim.")], None, verdicts=_verdicts())
        self.assertEqual(results, {})

    def test_missing_verdicts_is_a_noop(self):
        client = FakeConsistencyClient([])
        results = apply_consistency_pass([("a", "Some claim.")], client, verdicts=None)
        self.assertEqual(results, {})
        self.assertEqual(client.calls, 0)

    def test_failing_client_degrades_silently_with_a_warning(self):
        class _FailingClient:
            def complete_json(self, system, user, schema, *, effort=None):
                raise RuntimeError("boom")

        warnings: list[str] = []
        results = apply_consistency_pass(
            [("a", "Some claim.")], _FailingClient(), verdicts=_verdicts(), warn=warnings.append,
        )
        self.assertEqual(results, {})
        self.assertTrue(any("Consistency" in w for w in warnings))

    def test_reported_contradiction_is_applied(self):
        client = FakeConsistencyClient([
            {"location": "a", "quote": "used by every department company-wide",
             "correction": "used by the finance team"},
        ])
        results = apply_consistency_pass(
            [("a", "This report is used by every department company-wide.")],
            client, verdicts=_verdicts(),
        )
        self.assertEqual(results["a"], "This report is used by the finance team.")

    def test_quote_not_present_is_ignored(self):
        client = FakeConsistencyClient([
            {"location": "a", "quote": "nonexistent phrase", "correction": "x"},
        ])
        results = apply_consistency_pass([("a", "Some other text.")], client, verdicts=_verdicts())
        self.assertEqual(results, {})


class CheckConsistencyMergeTest(unittest.TestCase):
    def test_deterministic_and_llm_results_merge(self):
        client = FakeConsistencyClient([
            {"location": "b", "quote": "used by every department",
             "correction": "used by regional managers"},
        ])
        results = check_consistency(
            [("a", "This report is built on a well-structured star schema."),
             ("b", "This dashboard is used by every department.")],
            client, verdicts=_verdicts(is_star_schema=False,
                                       schema_shape="a snowflake schema (dimensions relate to other dimensions)"),
        )
        self.assertIn("snowflake schema", results["a"])
        self.assertEqual(results["b"], "This dashboard is used by regional managers.")

    def test_no_verdicts_available_is_a_noop(self):
        client = FakeConsistencyClient([{"location": "a", "quote": "x", "correction": "y"}])
        results = check_consistency([("a", "star schema x")], client, verdicts=None)
        self.assertEqual(results, {})
        self.assertEqual(client.calls, 0)


class ApplyResultsIntegrationTest(unittest.TestCase):
    def test_setters_receive_deterministic_consistency_corrections(self):
        sink = {}
        triples = [("a", "This report is a well-structured star schema design.",
                    lambda v: sink.__setitem__("a", v))]
        results = check_deterministic_consistency(
            [(loc, text) for loc, text, _ in triples],
            _verdicts(is_star_schema=False, schema_shape="a snowflake schema (dimensions relate to other dimensions)"),
        )
        apply_results(triples, results)
        self.assertIn("snowflake schema", sink["a"])


class ExecutiveGeneratorWiringTest(unittest.TestCase):
    """Day 2 end-to-end: a false star-schema claim seeded into the executive
    document's purpose, checked against audit verdicts, must be corrected in
    the final ExecutiveDocument via the same triples/apply_results mechanism
    the critic and grounding passes already use."""

    def test_false_star_schema_claim_is_corrected_against_audit_verdicts(self):
        model = _model()
        # Verdicts deliberately contradict this fixture's real shape — this
        # test exercises the wiring/correction mechanism, not whether
        # SampleSales itself happens to be a star schema (covered by
        # BuildAuditVerdictsTest instead).
        verdicts = _verdicts(is_star_schema=False,
                             schema_shape="a snowflake schema (dimensions relate to other dimensions)")

        doc = ExecutiveSummaryGenerator.generate(model)
        # Simulate an LLM having written a contradicting claim (offline mode
        # keeps generation deterministic, so we inject the contradiction the
        # same way GroundingGeneratorWiringTest does).
        doc.purpose = "This report is built on a well-structured star schema for fast analysis."

        from pbicompass.agents.generators.executive import _narrative_triples

        triples = _narrative_triples(doc)
        fields = [(loc, text) for loc, text, _ in triples]
        results = check_consistency(fields, None, verdicts=verdicts)
        apply_results(triples, results)

        self.assertNotIn("star schema", doc.purpose)
        self.assertIn("snowflake", doc.purpose.lower())


class _RlsContradictingClient:
    """A minimal LLMClient exercising every branch
    ``TechnicalDocumentationGenerator.generate`` calls with a client present,
    with the Business Analyst reporting a false "no RLS" claim — SampleSales
    genuinely defines 2 roles — so the generator's own internal
    ``_run_consistency`` call (wired into ``generate``, not invoked directly
    by the test) has a real contradiction to fix against the sibling Audit
    document's real verdicts."""

    def complete_json(self, system: str, user: str, schema: dict, *, effort: str | None = None) -> dict:
        if "consistency-checker" in system:
            # The false RLS claim is already fixed by the deterministic
            # layer before this LLM layer ever sees the text — nothing left
            # to report.
            return {"contradictions": []}
        if "fact-checker" in system:
            return {"claims": []}
        if "Report Intelligence" in system:
            return {
                "business_domain": "FAKE_DOMAIN",
                "report_purpose": {"statement": "FAKE_REPORT_PURPOSE", "confidence": "High"},
                "audience_hypotheses": [], "entity_definitions": [], "page_workflows": [],
                "kpi_relationships": [], "cross_cutting_observations": [], "data_quality_notes": [],
            }
        if "Business Analyst" in system or "BI consultant" in system:
            return {
                "core_purpose": "No row-level security is configured for this report.",
                "pages": [], "navigation_guide": [], "complex_visual_explainers": [],
            }
        if "senior DAX developer" in system or "DAX measures" in system:
            import json
            payload = json.loads(user)
            return {"translations": [
                {"name": m["name"], "plain_english": "A measure.",
                 "calculation_logic": "calc", "caveats": "", "category": "Other",
                 "confidence": "High"}
                for m in payload["measures"]
            ]}
        if "data-modeling" in system:
            return {"summary": "A model.", "risks": []}
        if "description for every column" in system or "Column Describer" in system:
            import json
            payload = json.loads(user)
            return {"columns": [
                {"table": c["table"], "column": c["column"], "description": "d"}
                for c in payload["columns"]
            ]}
        if "expert technical editor" in system:
            return {"violations": []}
        raise AssertionError(f"unexpected system prompt: {system[:60]}")


class TechnicalGeneratorConsistencyWiringTest(unittest.TestCase):
    """Day 2 "done when": a false RLS claim injected via a fake LLM client
    into the Business Analyst's output — checked entirely through
    ``TechnicalDocumentationGenerator.generate``'s own internal
    ``_run_consistency`` wiring, not by calling the consistency module
    directly — must be corrected in the final ``Document.executive_summary
    .core_purpose`` against the real, independently-computed Audit & Health
    Report verdict for this fixture (2 RLS roles). Deleting the
    ``_run_consistency(...)`` call from ``technical.py``'s ``generate``, or
    reverting ``check_deterministic_consistency``'s RLS check, makes this
    test fail."""

    def test_false_no_rls_claim_is_corrected_against_sibling_audit_doc(self):
        model = _model()
        self.assertEqual(len(model.roles), 2, "fixture must define RLS roles for this test to be meaningful")

        audit_doc = AuditReportGenerator.generate(model)
        verdicts = build_audit_verdicts(model, audit_doc)
        self.assertEqual(verdicts.rls_role_count, 2)

        doc = TechnicalDocumentationGenerator.generate(
            model, _RlsContradictingClient(), audit_verdicts=verdicts,
        )

        self.assertNotIn("No row-level security is configured", doc.executive_summary.core_purpose)
        self.assertIn("2 row-level security roles", doc.executive_summary.core_purpose)


if __name__ == "__main__":
    unittest.main(verbosity=2)
