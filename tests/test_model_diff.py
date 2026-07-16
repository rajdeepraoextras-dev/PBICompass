"""Tests for the C2 version-diff engine (``agents/model_diff.py``): coverage
across object types, impact analysis (usage → severity), and the two renderers.
"""
from __future__ import annotations

import unittest

from pbicompass.agents.model_diff import (
    compute_model_diff,
    generate_change_log_markdown,
    render_change_summary_html,
)


def _model(**over):
    base = {
        "report_name": "R",
        "tables": [
            {"name": "Sales",
             "columns": [{"name": "Amount"}, {"name": "Region"}],
             "measures": [{"name": "Total", "expression": "SUM(Sales[Amount])"},
                          {"name": "Margin", "expression": "[Total]*0.3"}]},
            {"name": "Geo", "columns": [{"name": "Region"}], "measures": []},
        ],
        "relationships": [{"from_table": "Sales", "from_column": "Region",
                           "to_table": "Geo", "to_column": "Region",
                           "cross_filter": "single", "is_active": True,
                           "from_cardinality": "many", "to_cardinality": "one"}],
        "roles": [{"name": "Regional", "table_permissions": [
            {"table": "Geo", "filter_expression": '[Region]="East"'}]}],
        "pages": [{"display_name": "Overview", "visuals": [
            {"fields": ["Sales.Total", "Sales.Margin"], "type": "card"}]}],
    }
    base.update(over)
    return base


class BackCompatTest(unittest.TestCase):
    def test_original_keys_preserved(self):
        old = {"tables": [{"name": "Sales", "columns": [{"name": "Amount"}],
                           "measures": [{"name": "Total", "expression": "SUM(x)"}]}],
               "relationships": []}
        new = {"tables": [{"name": "Sales", "columns": [{"name": "Amount"}],
                           "measures": [{"name": "Total", "expression": "SUM(x)*2"}]},
                          {"name": "Region", "columns": [{"name": "Name"}], "measures": []}],
               "relationships": []}
        d = compute_model_diff(old, new)
        self.assertEqual(d["added_tables"], ["Region"])
        self.assertEqual(list(d["changed_measures"].keys()), ["Total"])

    def test_no_change_message(self):
        self.assertIn("No structural or logic changes",
                      generate_change_log_markdown(compute_model_diff(_model(), _model())))


class ImpactAndSeverityTest(unittest.TestCase):
    def _entries(self, diff):
        return {(e["category"], e["name"]): e for e in diff["entries"]}

    def test_removed_used_measure_is_critical_with_impact(self):
        new = _model()
        del new["tables"][0]["measures"][1]  # remove Margin (used on Overview)
        e = self._entries(compute_model_diff(_model(), new))[("Measure", "Margin")]
        self.assertEqual(e["severity"], "Critical")
        self.assertIn("Overview", e["impact"])

    def test_removed_unused_measure_is_medium(self):
        old = _model()
        old["tables"][0]["measures"].append({"name": "Hidden", "expression": "1"})
        e = self._entries(compute_model_diff(old, _model()))[("Measure", "Hidden")]
        self.assertEqual(e["severity"], "Medium")

    def test_changed_used_measure_is_high(self):
        new = _model()
        new["tables"][0]["measures"][0]["expression"] = "SUM(Sales[Amount])*1.05"
        e = self._entries(compute_model_diff(_model(), new))[("Measure", "Total")]
        self.assertEqual(e["severity"], "High")

    def test_relationship_property_change_is_high(self):
        new = _model()
        new["relationships"][0]["cross_filter"] = "both"
        d = compute_model_diff(_model(), new)
        self.assertTrue(d["changed_relationships"])
        e = self._entries(d)[("Relationship", "Sales[Region] -> Geo[Region]")]
        self.assertEqual((e["kind"], e["severity"]), ("modified", "High"))

    def test_rls_filter_change_is_high_and_security_flagged(self):
        new = _model()
        new["roles"][0]["table_permissions"][0]["filter_expression"] = '[Region]="West"'
        e = self._entries(compute_model_diff(_model(), new))[("RLS role", "Regional")]
        self.assertEqual(e["severity"], "High")
        self.assertIn("Security", e["impact"])

    def test_removed_role_and_page(self):
        new = _model(roles=[], pages=[])
        d = compute_model_diff(_model(), new)
        cats = {(e["category"], e["kind"]) for e in d["entries"]}
        self.assertIn(("RLS role", "removed"), cats)
        self.assertIn(("Page", "removed"), cats)

    def test_feature_deltas(self):
        old = _model()
        old["tables"][0]["calculation_items"] = []
        new = _model()
        new["tables"][0]["calculation_items"] = [{"name": "YTD", "expression": "X"}]
        new["perspectives"] = [{"name": "Exec"}]
        new["cultures"] = [{"name": "fr-FR"}]
        cats = {e["category"] for e in compute_model_diff(old, new)["entries"]}
        self.assertIn("Calculation item", cats)
        self.assertIn("Perspective", cats)
        self.assertIn("Translation", cats)


class RenderTest(unittest.TestCase):
    def test_markdown_grouped_by_severity(self):
        new = _model()
        del new["tables"][0]["measures"][1]
        md = generate_change_log_markdown(compute_model_diff(_model(), new))
        self.assertIn("**Critical**", md)
        self.assertIn("Margin", md)
        self.assertIn("change(s) since the last version", md)

    def test_html_is_self_contained(self):
        new = _model()
        new["relationships"][0]["is_active"] = False
        html = render_change_summary_html(compute_model_diff(_model(), new), title="What Changed")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("What Changed", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)  # no external assets

    def test_html_no_changes(self):
        html = render_change_summary_html(compute_model_diff(_model(), _model()))
        self.assertIn("No structural or logic changes", html)


if __name__ == "__main__":
    unittest.main()
