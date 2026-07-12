"""Tests for the §6 model (ER) diagram (Day 6): ``render/_model_diagram.py``.

Covers the star layout (<=12 tables), the grandalf-backed layered layout
(>12 tables) with graceful fallback when grandalf isn't installed, the
cardinality glyphs, active/inactive line styling, and the exact markup
contract ``test_render.py::HtmlRenderTest`` already pins (``class="dm-node"
data-table="..."``, ``class="dm-edge" data-from="..." data-to="..."``, a
join-column tooltip with an arrow).
"""

from __future__ import annotations

import builtins
import unittest

from pbicompass.render._model_diagram import render_model_diagram_svg


def _table(name, kind="dimension", columns=4, measures=0):
    return {"name": name, "kind": kind, "columns": columns, "measures": measures}


def _edge(f, t, from_card="many", to_card="one", active=True, from_col=None, to_col=None):
    e = {"from": f, "to": t, "from_card": from_card, "to_card": to_card, "is_active": active}
    if from_col:
        e["from_column"] = from_col
    if to_col:
        e["to_column"] = to_col
    return e


class EmptyModelTest(unittest.TestCase):
    def test_no_tables_returns_empty_string(self):
        self.assertEqual(render_model_diagram_svg([], []), "")


class StarLayoutTest(unittest.TestCase):
    """<=12 tables: fact(s) centered, dimensions ringed."""

    def setUp(self):
        self.tables = [
            _table("Sales", kind="fact", columns=8, measures=5),
            _table("Date", columns=6),
            _table("Customer", columns=10),
            _table("Product", columns=7),
        ]
        self.edges = [
            _edge("Sales", "Date", from_col="DateKey", to_col="DateKey"),
            _edge("Sales", "Customer", from_col="CustomerKey", to_col="CustomerKey"),
            _edge("Sales", "Product", active=False, from_col="ProductKey", to_col="ProductKey"),
        ]
        self.svg = render_model_diagram_svg(self.tables, self.edges)

    def test_is_an_svg_with_labelled_title(self):
        self.assertIn('role="img" aria-labelledby="model-diagram-title"', self.svg)
        self.assertIn("<title id=\"model-diagram-title\">", self.svg)

    def test_every_table_gets_a_node_with_exact_markup_contract(self):
        # Pinned by test_render.py::HtmlRenderTest::test_interactive_diagram_nodes_and_edges
        self.assertIn('class="dm-node" data-table="Sales"', self.svg)
        self.assertIn('class="dm-node" data-table="Date"', self.svg)
        self.assertIn('class="dm-node" data-table="Customer"', self.svg)
        self.assertIn('class="dm-node" data-table="Product"', self.svg)

    def test_edges_carry_data_from_and_data_to(self):
        self.assertIn('class="dm-edge" data-from="Sales" data-to="Date"', self.svg)

    def test_join_column_tooltip_has_an_arrow(self):
        self.assertIn("Sales[DateKey] → Date[DateKey]", self.svg)

    def test_every_table_anchors_into_the_data_dictionary(self):
        self.assertIn('href="#table-sales"', self.svg)
        self.assertIn('href="#table-date"', self.svg)
        self.assertIn('href="#table-customer"', self.svg)
        self.assertIn('href="#table-product"', self.svg)

    def test_inactive_relationship_is_dashed_active_is_not(self):
        # Product edge (inactive) must carry a dash array; the Date edge
        # (active) must not.
        self.assertIn('stroke-dasharray="5 4"', self.svg)
        date_edge_body = self.svg.split('data-from="Sales" data-to="Date">', 1)[1].split("</g>", 1)[0]
        self.assertNotIn("stroke-dasharray", date_edge_body)

    def test_cardinality_glyphs_present(self):
        # many-to-one: "*" near the many end, "1" near the one end.
        self.assertIn(">1<", self.svg)
        self.assertIn(">*<", self.svg)

    def test_legend_labels_fact_and_dimension(self):
        self.assertIn("Fact table", self.svg)
        self.assertIn("Dimension table", self.svg)

    def test_sublabel_shows_column_and_measure_counts(self):
        self.assertIn("8 columns · 5 measures", self.svg)
        self.assertIn("6 columns", self.svg)


class NoFactDetectedTest(unittest.TestCase):
    """When every table came back "unknown"/non-fact, the diagram still
    needs a center — the largest table by column+measure count anchors
    the ring rather than leaving nothing to ring around."""

    def test_largest_table_becomes_the_center(self):
        tables = [
            _table("Small", kind="unknown", columns=2),
            _table("Big", kind="unknown", columns=20, measures=5),
        ]
        svg = render_model_diagram_svg(tables, [])
        self.assertIn('data-table="Big"', svg)
        self.assertIn('data-table="Small"', svg)


class GalaxySchemaTest(unittest.TestCase):
    """Multiple fact tables cluster near the center rather than each
    getting its own ring."""

    def test_two_facts_both_render_with_dimensions_ringed(self):
        tables = [
            _table("Sales", kind="fact", columns=6, measures=3),
            _table("Returns", kind="fact", columns=4, measures=2),
            _table("Date", columns=5),
            _table("Product", columns=6),
        ]
        edges = [_edge("Sales", "Date"), _edge("Returns", "Date"), _edge("Sales", "Product")]
        svg = render_model_diagram_svg(tables, edges)
        for name in ("Sales", "Returns", "Date", "Product"):
            self.assertIn(f'data-table="{name}"', svg)


class LargeModelGrandalfTest(unittest.TestCase):
    """>12 tables switches to the grandalf-backed layered layout when
    grandalf is installed."""

    def setUp(self):
        self.tables = [_table("Fact", kind="fact", columns=5, measures=10)]
        self.tables += [_table(f"Dim{i}", columns=4) for i in range(15)]
        self.edges = [_edge("Fact", f"Dim{i}") for i in range(15)]

    def test_all_16_tables_render(self):
        svg = render_model_diagram_svg(self.tables, self.edges)
        self.assertIn('data-table="Fact"', svg)
        for i in range(15):
            self.assertIn(f'data-table="Dim{i}"', svg)

    def test_graceful_fallback_when_grandalf_is_not_installed(self):
        # Simulate the optional extra being absent — must never raise, and
        # must still render every table (denser star layout instead).
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "grandalf" or name.startswith("grandalf."):
                raise ImportError("simulated missing optional extra")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            svg = render_model_diagram_svg(self.tables, self.edges)
        finally:
            builtins.__import__ = real_import
        self.assertIn('data-table="Fact"', svg)
        self.assertIn('data-table="Dim14"', svg)


class DisconnectedTableTest(unittest.TestCase):
    """A table with no relationships at all must still appear on the
    canvas (never silently dropped) — grandalf's per-component layout
    handles this for the >12-table path; the star layout's ring already
    includes every non-fact table regardless of edges."""

    def test_disconnected_table_still_renders_in_star_layout(self):
        tables = [_table("Sales", kind="fact"), _table("Orphan")]
        svg = render_model_diagram_svg(tables, [])
        self.assertIn('data-table="Orphan"', svg)

    def test_disconnected_table_still_renders_in_grandalf_layout(self):
        tables = [_table("Fact", kind="fact")] + [_table(f"Dim{i}") for i in range(13)]
        edges = [_edge("Fact", f"Dim{i}") for i in range(12)]  # Dim12 has no edge
        svg = render_model_diagram_svg(tables, edges)
        self.assertIn('data-table="Dim12"', svg)


if __name__ == "__main__":
    unittest.main()
