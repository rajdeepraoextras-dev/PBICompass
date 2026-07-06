"""Tests for ``pbicompass.render._wireframe`` — the page-wireframe SVG (3.1),
redesigned per J.C (also fixes I3's dead links).
"""

from __future__ import annotations

import re
import unittest

from pbicompass.render._wireframe import render_wireframe
from pbicompass.schemas.model import Page, Visual


def _page(visuals, *, width=1280, height=720) -> Page:
    return Page(id="p1", display_name="IT Spend Trend", width=width, height=height, visuals=visuals)


class FriendlyTypeNameTest(unittest.TestCase):
    """J.C item 2: never render a camelCase internal visualType name."""

    def test_combo_chart_type_gets_a_friendly_name(self):
        page = _page([Visual(id="v1", type="lineStackedColumnComboChart", title="Var Plan % by Country/Region",
                             x=0, y=0, z=0, width=300, height=200,
                             fields=["Sales.VarPlanPct", "Geo.Country"])])
        svg = render_wireframe(page)
        self.assertIn("Combo chart", svg)
        self.assertNotIn("lineStackedColumnComboChart", svg)

    def test_decomposition_tree_without_visual_suffix_gets_a_friendly_name(self):
        page = _page([Visual(id="v1", type="decompositionTree", title="Drivers",
                             x=0, y=0, z=0, width=300, height=200, fields=["Sales.Amount"])])
        svg = render_wireframe(page)
        self.assertIn("Decomposition tree", svg)
        self.assertNotIn("decompositionTree", svg)

    def test_stacked_area_chart_gets_a_friendly_name(self):
        page = _page([Visual(id="v1", type="stackedAreaChart", title="Trend",
                             x=0, y=0, z=0, width=300, height=200, fields=["Sales.Amount"])])
        svg = render_wireframe(page)
        self.assertIn("Area chart", svg)
        self.assertNotIn("stackedAreaChart", svg)

    def test_no_camelcase_type_name_ever_leaks_for_any_known_type(self):
        from pbicompass.agents.report_facts import FRIENDLY_VISUAL

        visuals = [
            Visual(id=f"v{i}", type=t, title=f"Visual {i}", x=(i % 4) * 100, y=(i // 4) * 100, z=0,
                  width=90, height=70, fields=["Sales.Amount"])
            for i, t in enumerate(FRIENDLY_VISUAL)
        ]
        svg = render_wireframe(_page(visuals, width=1600, height=900))
        camel_case_leak = re.search(r">[a-z][a-zA-Z]*[A-Z][a-zA-Z]*<", svg)
        self.assertIsNone(camel_case_leak, f"camelCase type name leaked into text: {camel_case_leak}")


class CleanMarkupTest(unittest.TestCase):
    """J.C item 8: no inline style=/onmouseover=/onmouseout= — hover lives in
    the shared shell's CSS via a .wf-node class instead."""

    def test_no_inline_style_or_event_handlers(self):
        page = _page([
            Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                  width=300, height=200, fields=["Sales.Revenue", "Date.Month"]),
            Visual(id="v2", type="slicer", is_slicer=True, x=310, y=0, z=0, width=100, height=80,
                  fields=["Date.Year"]),
        ])
        wrapper = render_wireframe(page)
        svg_only = wrapper.split("</svg>", 1)[0]  # legend swatches (outside <svg>) use
                                                    # the same inline-style convention as
                                                    # the model diagram's own legend
        self.assertNotIn("onmouseover", svg_only)
        self.assertNotIn("onmouseout", svg_only)
        self.assertNotIn("style=", svg_only)
        self.assertIn('class="wf-node"', svg_only)


class LinkCategoryTest(unittest.TestCase):
    """I3: only data visuals link to their table row; slicers link to the
    page card (where the filter list lives); buttons/shapes/text/images
    render unlinked rather than pointing at a row that doesn't exist."""

    def test_data_visual_links_to_its_visual_anchor(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue", "Date.Month"])])
        svg = render_wireframe(page)
        self.assertIn('href="#visual-it-spend-trend-revenue-by-month"', svg)

    def test_slicer_links_to_the_page_anchor_not_a_visual_row(self):
        page = _page([Visual(id="v1", type="slicer", is_slicer=True, title="Year", x=0, y=0, z=0,
                             width=100, height=80, fields=["Date.Year"])])
        svg = render_wireframe(page)
        self.assertIn('href="#page-it-spend-trend"', svg)
        self.assertNotIn("href=\"#visual-", svg)

    def test_button_and_decorative_visuals_are_not_linked(self):
        page = _page([
            Visual(id="v1", type="actionButton", x=0, y=0, z=0, width=100, height=40),
            Visual(id="v2", type="basicShape", x=110, y=0, z=0, width=100, height=40),
            Visual(id="v3", type="textbox", x=220, y=0, z=0, width=100, height=40),
        ])
        svg = render_wireframe(page)
        self.assertNotIn("<a ", svg)


class TinyObjectAndOverflowTest(unittest.TestCase):
    """J.C item 6: sub-threshold objects collapse to a dot; 3+ decorative
    objects fold into a footer note instead of a wall of near-identical
    rectangles."""

    def test_tiny_object_renders_as_an_unlinked_dot(self):
        # 1280x720 page area = 921,600; a 5x5 visual is ~0.0027% of that.
        page = _page([Visual(id="v1", type="shape", x=0, y=0, z=0, width=5, height=5)])
        svg = render_wireframe(page)
        self.assertIn("<circle", svg)
        self.assertNotIn("<a ", svg)

    def test_three_or_more_decorative_shapes_collapse_with_a_footer_note(self):
        visuals = [Visual(id=f"v{i}", type="shape", x=i * 150, y=0, z=0, width=120, height=100)
                  for i in range(5)]
        svg = render_wireframe(_page(visuals))
        self.assertIn("wf-footer", svg)
        self.assertIn("decorative shape", svg)


class LegendAndTooltipTest(unittest.TestCase):
    def test_legend_present(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn("Data visual", svg)
        self.assertIn("Slicer", svg)
        self.assertIn("Navigation", svg)
        self.assertIn("Decorative", svg)

    def test_data_visual_has_a_native_tooltip_naming_type_and_fields(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue", "Date.Month"])])
        svg = render_wireframe(page)
        self.assertIn("Revenue by Month — Column chart (Revenue, Month)", svg)

    def test_returns_empty_string_without_layout_coordinates(self):
        page = Page(id="p1", display_name="No Layout", visuals=[Visual(id="v1", type="card")])
        self.assertEqual(render_wireframe(page), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
