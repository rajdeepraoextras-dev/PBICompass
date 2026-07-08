"""Tests for ``pbicompass.agents.report_facts`` — pure functions turning a
``SemanticModel`` into structured page/visual/slicer facts shared by every
document generator.
"""

from __future__ import annotations

import unittest

from pbicompass.agents.report_facts import (
    FIELD_SELECTOR_LABEL,
    business_plain_english,
    declassify,
    field_parameter_table_names,
    first_sentence,
    is_field_selector,
    local_path_sources,
    report_pages,
    simplify_dax_prose,
    slicers,
)
from pbicompass.schemas.model import Column, DataSource, Measure, Page, SemanticModel, Table, Visual


def _model_with_duplicate_visuals() -> SemanticModel:
    table = Table(name="Sales", measures=[Measure(name="Sale_Value", expression="SUM(Sales[Amount])", table="Sales")])
    page = Page(
        id="p1", display_name="Overview",
        visuals=[Visual(id=f"v{i}", type="card", fields=["Sales.Sale_Value"]) for i in range(5)],
    )
    return SemanticModel(report_name="R", tables=[table], pages=[page])


def _model_with_duplicate_slicers() -> SemanticModel:
    page = Page(
        id="p1", display_name="Overview",
        visuals=[
            Visual(id="s1", type="slicer", is_slicer=True, fields=["Sales.Type"]),
            Visual(id="s2", type="slicer", is_slicer=True, fields=["Sales.Type"]),
        ],
    )
    return SemanticModel(report_name="R", pages=[page])


class ReportPagesDedupeTest(unittest.TestCase):
    """1.2: identical visuals collapse into one row with a count, instead of
    one near-duplicate row per instance."""

    def test_identical_visuals_collapse_with_count(self):
        pages = report_pages(_model_with_duplicate_visuals())
        visuals = pages[0]["visuals"]
        self.assertEqual(len(visuals), 1)
        self.assertEqual(visuals[0]["count"], 5)
        self.assertIn("×5", visuals[0]["label"])

    def test_distinct_visuals_are_not_merged(self):
        table = Table(name="Sales", measures=[
            Measure(name="A", expression="SUM(Sales[X])", table="Sales"),
            Measure(name="B", expression="SUM(Sales[Y])", table="Sales"),
        ])
        page = Page(id="p1", display_name="Overview", visuals=[
            Visual(id="v1", type="card", fields=["Sales.A"]),
            Visual(id="v2", type="card", fields=["Sales.B"]),
        ])
        pages = report_pages(SemanticModel(report_name="R", tables=[table], pages=[page]))
        self.assertEqual(len(pages[0]["visuals"]), 2)
        self.assertTrue(all(v["count"] == 1 for v in pages[0]["visuals"]))


class SlicersDedupeTest(unittest.TestCase):
    """1.7: two slicer visuals bound to the same field on the same page
    collapse into one row, noting the multiplicity via ``count``."""

    def test_same_field_same_page_collapses(self):
        rows = slicers(_model_with_duplicate_slicers())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["field"], "Sales.Type")


def _model_with_field_parameter() -> SemanticModel:
    """A disconnected, calculated 'select' table driving a chart's axis —
    the exact I4 shape: field parameters are calculated tables, never
    joined via a relationship, typically with a handful of columns."""
    sales = Table(name="Sales", kind="fact", measures=[
        Measure(name="Actual", expression="SUM(Sales[Amount])", table="Sales"),
    ])
    selector = Table(name="select", is_calculated=True, columns=[
        Column(name="select"), Column(name="select Order"), Column(name="select Fields"),
    ])
    page = Page(
        id="p1", display_name="Overview",
        visuals=[Visual(id="v1", type="columnChart", fields=["Sales.Actual", "select.select"])],
    )
    return SemanticModel(report_name="R", tables=[sales, selector], pages=[page])


class FieldParameterRecognitionTest(unittest.TestCase):
    """I4: field parameters / disconnected helper tables must not leak into
    generated dimensions, business questions, or the glossary as if they
    were real report data."""

    def test_field_parameter_table_is_recognized(self):
        names = field_parameter_table_names(_model_with_field_parameter())
        self.assertIn("select", names)

    def test_related_calculated_table_is_not_flagged(self):
        # A calculated table that *is* joined to the model is real content,
        # not a field parameter — e.g. a calculated date table.
        date_tbl = Table(name="Calendar", is_calculated=True,
                         columns=[Column(name="Date"), Column(name="Year"), Column(name="Month")])
        sales = Table(name="Sales", kind="fact", columns=[Column(name="Date")])
        from pbicompass.schemas.model import Relationship
        model = SemanticModel(
            report_name="R", tables=[sales, date_tbl],
            relationships=[Relationship(from_table="Sales", from_column="Date",
                                        to_table="Calendar", to_column="Date")],
        )
        self.assertEqual(field_parameter_table_names(model), set())

    def test_field_parameter_excluded_from_report_pages_dimensions(self):
        pages = report_pages(_model_with_field_parameter())
        visuals = pages[0]["visuals"]
        all_dims = [d for v in visuals for d in v["dimensions"]]
        self.assertNotIn("select", all_dims)
        self.assertIn("Actual", [m for v in visuals for m in v["metrics"]])

    def test_field_parameter_excluded_from_business_questions(self):
        from pbicompass.agents.deterministic import business_analyst_deterministic

        summary = business_analyst_deterministic(_model_with_field_parameter())
        questions = summary.pages[0].business_questions
        self.assertFalse(any("select" in q for q in questions),
                         f"field parameter leaked into a question: {questions}")

    def test_field_parameter_labeled_as_selector_in_glossary(self):
        from pbicompass.agents.generators.user_guide import BusinessGuideGenerator

        doc = BusinessGuideGenerator.generate(_model_with_field_parameter())
        term = next((g for g in doc.glossary if g.term == "select"), None)
        self.assertIsNotNone(term)
        self.assertIn("field selector", term.plain_definition.lower())


def _model_with_bare_field_parameter() -> SemanticModel:
    """D4 regression: Power BI's report layout sometimes emits a field-
    parameter projection as a bare, unqualified ``queryRef`` — just the
    parameter table's own name ("select"/"select1"), with no
    ``Entity.Property`` qualification at all (see
    ``parsers/pbir.py::_extract_fields``'s ``queryRef`` fallback).
    Reproduces the exact production shape: the parameter table doesn't even
    appear in ``model.tables`` (dropped somewhere upstream of the report
    layout), so there is no dot to strip a table name from and no table
    object for ``field_parameter_table_names()`` to have recognized in the
    first place — only the bare token's own name gives it away."""
    sales = Table(name="Sales", kind="fact", measures=[
        Measure(name="Actual", expression="SUM(Sales[Amount])", table="Sales"),
    ])
    page = Page(
        id="p1", display_name="Overview",
        visuals=[
            Visual(id="v1", type="lineStackedColumnComboChart",
                   fields=["select", "select1", "Sales.Actual"]),
            Visual(id="s1", type="slicer", is_slicer=True, fields=["select1"]),
        ],
    )
    return SemanticModel(report_name="R", tables=[sales], pages=[page])


class BareFieldSelectorRegressionTest(unittest.TestCase):
    """D4: a field-parameter reference shaped as a bare, unqualified token
    (no table object in ``model.tables``, no ``.`` to split) must be
    recognized just like the qualified ``Table.Column`` shape — everywhere
    ``report_facts``'s I4 filtering already applied to the qualified case."""

    def test_is_field_selector_recognizes_bare_telltale_names(self):
        self.assertTrue(is_field_selector("select", set()))
        self.assertTrue(is_field_selector("select1", set()))
        self.assertTrue(is_field_selector("Range", set()))
        self.assertTrue(is_field_selector("Field Parameter", set()))
        self.assertFalse(is_field_selector("Business Area", set()))
        self.assertFalse(is_field_selector("Sales.Actual", set()))

    def test_bare_field_parameter_excluded_from_visual_title_and_dimensions(self):
        pages = report_pages(_model_with_bare_field_parameter())
        visuals = pages[0]["visuals"]
        self.assertEqual(len(visuals), 1)  # the slicer visual is never a "visual" row (I3)
        combo = visuals[0]
        self.assertNotIn("select", combo["dimensions"])
        self.assertNotIn("select1", combo["dimensions"])
        self.assertEqual(combo["label"], "Actual")

    def test_bare_field_parameter_excluded_from_business_questions(self):
        from pbicompass.agents.deterministic import business_analyst_deterministic

        summary = business_analyst_deterministic(_model_with_bare_field_parameter())
        questions = summary.pages[0].business_questions
        self.assertFalse(any("select" in q for q in questions),
                         f"bare field parameter leaked into a question: {questions}")

    def test_bare_field_parameter_excluded_from_page_theme(self):
        from pbicompass.agents.deterministic import business_analyst_deterministic

        summary = business_analyst_deterministic(_model_with_bare_field_parameter())
        self.assertNotIn("select", summary.pages[0].summary)

    def test_bare_field_parameter_slicer_relabeled(self):
        rows = slicers(_model_with_bare_field_parameter())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["field"], FIELD_SELECTOR_LABEL)

    def test_bare_field_parameter_nav_guide_relabeled(self):
        from pbicompass.agents.deterministic import business_analyst_deterministic

        summary = business_analyst_deterministic(_model_with_bare_field_parameter())
        nav_text = " ".join(summary.navigation_guide)
        self.assertNotIn("select1", nav_text)
        self.assertIn(FIELD_SELECTOR_LABEL, nav_text)

    def test_bare_field_parameter_excluded_from_technical_glossary(self):
        from pbicompass.agents.generators.technical import TechnicalDocumentationGenerator

        doc = TechnicalDocumentationGenerator.generate(_model_with_bare_field_parameter())
        terms = {e["term"] for e in doc.glossary_entries}
        self.assertNotIn("select", terms)
        self.assertNotIn("select1", terms)

    def test_bare_field_parameter_labeled_as_selector_in_user_guide_glossary(self):
        from pbicompass.agents.generators.user_guide import BusinessGuideGenerator

        doc = BusinessGuideGenerator.generate(_model_with_bare_field_parameter())
        for name in ("select", "select1"):
            term = next((g for g in doc.glossary if g.term == name), None)
            self.assertIsNotNone(term, f"expected a glossary entry for {name!r}")
            self.assertIn("field selector", term.plain_definition.lower())


class LocalPathSourcesTest(unittest.TestCase):
    def test_detects_drive_letter_and_user_profile_paths(self):
        model = SemanticModel(
            report_name="R",
            data_sources=[
                DataSource(type="Excel.Workbook", detail=r"C:\Users\faisal\Desktop\orders.xlsx"),
                DataSource(type="Sql.Database", server="prod-sql.contoso.com", database="SalesDW"),
            ],
        )
        paths = local_path_sources(model)
        self.assertEqual(len(paths), 1)
        self.assertIn("orders.xlsx", paths[0])


class FirstSentenceTest(unittest.TestCase):
    def test_returns_only_the_first_sentence(self):
        self.assertEqual(first_sentence("First one. Second one."), "First one.")

    def test_returns_whole_text_when_no_terminator(self):
        self.assertEqual(first_sentence("No terminator here"), "No terminator here")

    def test_empty_input(self):
        self.assertEqual(first_sentence(""), "")
        self.assertEqual(first_sentence(None), "")


class SimplifyDaxProseTest(unittest.TestCase):
    """P3: a business-facing fallback must never leak raw DAX aggregation
    syntax, even nested inside another function's argument."""

    def test_distinctcount_becomes_plain_english(self):
        self.assertEqual(
            simplify_dax_prose("DISTINCTCOUNT ( Sales[SalesKey] )"),
            "the number of unique Sales[SalesKey] values",
        )

    def test_nested_inside_divide_is_also_simplified(self):
        text = "A ratio: Total Revenue divided by DISTINCTCOUNT ( Sales[SalesKey] )."
        simplified = simplify_dax_prose(text)
        self.assertNotIn("DISTINCTCOUNT", simplified)
        self.assertIn("the number of unique Sales[SalesKey] values", simplified)

    def test_countrows_and_sum_are_simplified(self):
        self.assertIn("the number of Sales rows", simplify_dax_prose("COUNTROWS ( Sales )"))
        self.assertIn("the total Sales[Amount]", simplify_dax_prose("SUM ( Sales[Amount] )"))

    def test_text_without_dax_calls_is_unchanged(self):
        self.assertEqual(simplify_dax_prose("A plain sentence."), "A plain sentence.")


class BusinessPlainEnglishTest(unittest.TestCase):
    def test_never_leaks_raw_function_syntax_or_brackets(self):
        # Regression (P3): "Avg Order Value" style measures used to render as
        # "A ratio: Total Revenue divided by DISTINCTCOUNT ( Sales[SalesKey] )."
        # in business-facing docs — should now read in plain English.
        text = business_plain_english(
            "Avg Order Value", "DIVIDE ( [Total Revenue], DISTINCTCOUNT ( Sales[SalesKey] ) )", None,
        )
        self.assertNotIn("DISTINCTCOUNT", text)
        self.assertNotIn("[", text)
        self.assertIn("number of unique", text)

    def test_declassify_still_strips_bracket_notation(self):
        self.assertEqual(declassify("Sales[Quantity] * Sales[UnitPrice]"), "Quantity * UnitPrice")


if __name__ == "__main__":
    unittest.main(verbosity=2)
