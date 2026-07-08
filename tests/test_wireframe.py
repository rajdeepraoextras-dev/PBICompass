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
    """J.C item 8 / Day-12 done-when: no inline style=/onmouseover=/onmouseout=
    anywhere in the output — hover, focus, and the legend swatches all live in
    the shared shell's CSS (.wf-node / .swatch--* classes) instead."""

    def test_no_inline_style_or_event_handlers(self):
        page = _page([
            Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                  width=300, height=200, fields=["Sales.Revenue", "Date.Month"]),
            Visual(id="v2", type="slicer", is_slicer=True, x=310, y=0, z=0, width=100, height=80,
                  fields=["Date.Year"]),
        ])
        wrapper = render_wireframe(page)  # whole wrapper, legend included
        self.assertNotIn("onmouseover", wrapper)
        self.assertNotIn("onmouseout", wrapper)
        self.assertNotIn("style=", wrapper)          # incl. the legend chips
        self.assertIn('class="wf-node cat-data"', wrapper)
        self.assertIn('class="wf-chip-dot wf-chip-dot--data"', wrapper)


class OnCanvasLabelTest(unittest.TestCase):
    """Day-12: the on-canvas text is the visual's real title + friendly type,
    never the "WIP" placeholder the temporary hack left behind."""

    def test_large_visual_renders_real_title_and_type_not_wip(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue", "Date.Month"])])
        svg = render_wireframe(page)
        self.assertNotIn("WIP", svg)
        self.assertIn(">Revenue by Month</text>", svg)   # on-canvas title (600-weight)
        self.assertIn(">Column chart</text>", svg)        # on-canvas friendly type

    def test_long_title_is_truncated_on_canvas(self):
        page = _page([Visual(id="v1", type="columnChart",
                             title="Revenue by Month and Region and Product Line",
                             x=0, y=0, z=0, width=300, height=200, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn("…</text>", svg)                    # truncated with an ellipsis
        self.assertNotIn("Product Line</text>", svg)      # tail dropped on-canvas

    def test_medium_visual_renders_friendly_type_not_wip(self):
        # Thresholds are in *scaled* units (x0.375 at 1280px wide): 120x55 px
        # -> 45x20.6, the medium tier (>=35x18, <60x24): friendly type only.
        page = _page([Visual(id="v1", type="lineChart", title="Trend", x=0, y=0, z=0,
                             width=120, height=55, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertNotIn("WIP", svg)
        self.assertIn(">Line chart</text>", svg)


class UppercaseTextTest(unittest.TestCase):
    """All on-canvas + legend text renders uppercase (scoped to the wireframe
    via CSS text-transform, so the underlying titles/anchors keep real case)."""

    def test_svg_style_uppercases_on_canvas_text(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue by Month", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue", "Date.Month"])])
        svg = render_wireframe(page)
        self.assertIn("text-transform: uppercase", svg)
        # CSS-only: the DOM text keeps its real case (tooltips/anchors depend on it)
        self.assertIn(">Revenue by Month</text>", svg)

    def test_legend_uses_the_uppercase_modifier(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn('class="legend legend--upper wf-legend"', svg)


class V4DesignSystemTest(unittest.TestCase):
    """Day 13 addendum: the wireframe re-skinned in the user-supplied
    wireframe-v4-light.html's exact visual language (colors, cards, icons)
    applied to real per-visual positions ("Option A", confirmed by the
    user against a mockup artifact) — replacing v2's tinted-fill boxes."""

    def test_data_visual_uses_the_v4_accent_and_card_structure(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn('class="wf-card-bg cat-data" fill="#ffffff"', svg)  # neutral white surface
        self.assertIn('fill="#4f6ef7"', svg)  # v4's exact data accent (top bar / icon)
        self.assertIn('fill="#eef1fe"', svg)  # v4's exact data icon-badge tint

    def test_every_category_gets_its_own_v4_accent(self):
        page = _page([
            Visual(id="v1", type="slicer", is_slicer=True, title="Region", x=0, y=0, z=0, width=150, height=100, fields=["Geo.Region"]),
            Visual(id="v2", type="actionButton", title="Go", x=160, y=0, z=0, width=150, height=60),
            Visual(id="v3", type="textbox", title="Note", x=320, y=0, z=0, width=150, height=60),
        ])
        svg = render_wireframe(page)
        self.assertIn('fill="#f59e0b"', svg)  # slicer accent
        self.assertIn('fill="#10b981"', svg)  # nav accent
        self.assertIn('fill="#8b5cf6"', svg)  # decorative accent

    def test_every_category_now_gets_an_icon_not_just_data_and_slicer(self):
        # v2 only iconified data visuals (+ a generic slicer funnel); v4
        # gives nav buttons and each decorative kind their own icon too.
        page = _page([
            Visual(id="v1", type="actionButton", title="View Details", x=0, y=0, z=0, width=150, height=60),
            Visual(id="v2", type="image", title="Logo", x=160, y=0, z=0, width=150, height=150),
            Visual(id="v3", type="textbox", title="Note", x=320, y=0, z=0, width=150, height=60),
        ])
        svg = render_wireframe(page)
        self.assertIn("wf-i-button-", svg)
        self.assertIn("wf-i-image-", svg)
        self.assertIn("wf-i-textbox-", svg)

    def test_dimension_tag_shows_the_real_box_size(self):
        page = _page([Visual(id="v1", type="card", title="Total Revenue", x=0, y=0, z=0,
                             width=277, height=123, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn('class="wf-tag"', svg)
        self.assertIn(">277 × 123<", svg)

    def test_kpi_card_gets_ghost_value_when_roomy(self):
        page = _page([Visual(id="v1", type="card", title="Total Revenue", x=0, y=0, z=0,
                             width=277, height=123, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn("▬▬.▬", svg)  # placeholder — never a real/invented number

    def test_bar_chart_gets_ghost_bars_when_roomy(self):
        page = _page([Visual(id="v1", type="columnChart", title="Revenue by Region", x=0, y=0, z=0,
                             width=450, height=400, fields=["Sales.Revenue", "Geo.Region"])])
        svg = render_wireframe(page)
        self.assertIn("wf-dotbg-", svg)
        self.assertGreaterEqual(svg.count('rx="0.8" fill="#4f6ef7"'), 4)  # multiple bars

    def test_line_chart_gets_a_ghost_line_when_roomy(self):
        page = _page([Visual(id="v1", type="lineChart", title="Monthly Trend", x=0, y=0, z=0,
                             width=420, height=200, fields=["Sales.Revenue"])])
        svg = render_wireframe(page)
        self.assertIn("wf-line-grad-", svg)

    def test_map_gets_ghost_dots_when_roomy(self):
        page = _page([Visual(id="v1", type="map", title="Sales by State", x=0, y=0, z=0,
                             width=420, height=250, fields=["Sales.Revenue", "Geo.State"])])
        svg = render_wireframe(page)
        # multiple dots beyond the tiny-object-collapse circle
        self.assertGreaterEqual(svg.count('fill="#4f6ef7" opacity='), 3)

    def test_small_kpi_card_gets_no_ghost_content(self):
        # A real, small KPI card (below the ghost-content room threshold)
        # still gets the card chrome but no cramped mini-sparkline.
        page = _page([Visual(id="v1", type="card", title="Orders", x=0, y=0, z=0,
                             width=90, height=50, fields=["Sales.Orders"])])
        svg = render_wireframe(page)
        self.assertNotIn("▬▬.▬", svg)

    def test_no_legacy_swatch_modifier_classes_survive(self):
        # Day-12's swatch--* scheme is fully replaced by wf-chip pills.
        page = _page([Visual(id="v1", type="columnChart", title="Revenue", x=0, y=0, z=0,
                             width=300, height=200, fields=["Sales.Revenue"])])
        self.assertNotIn("swatch--", render_wireframe(page))


class VisualAnchorMapTest(unittest.TestCase):
    """Day 13 / I3: report_pages() relabels 2+ identical visuals into one
    "Label — Type ×N" table row and dedupe_ids() resolves any remaining
    slug collision between different rows — the wireframe's own <a href>
    must land on that *resolved* anchor, not an independently recomputed
    raw one, or it's a dead/wrong link the moment a page has duplicate or
    slug-colliding visuals (both real, common shapes: repeated KPI cards;
    two differently-worded titles that strip down to the same slug)."""

    def test_anchor_map_resolves_the_grouped_relabel(self):
        page = _page([Visual(id="v1", type="card", title="Sale Value", x=0, y=0, z=0,
                             width=90, height=70, fields=["Sales.Sale_Value"])])
        # Simulates what report_pages() computes once 2+ identical cards get
        # merged into one "Sale Value — Card ×2" row. Key order/shape must
        # match _wireframe.py's own: (title, friendly_type, metrics, dims).
        key = ("Sale Value", "Card", frozenset({"Sale_Value"}), frozenset())
        svg = render_wireframe(page, measure_names=frozenset({"Sale_Value"}),
                               visual_anchor_map={key: "sale-value-card-2"})
        self.assertIn('href="#visual-it-spend-trend-sale-value-card-2"', svg)
        self.assertNotIn('href="#visual-it-spend-trend-sale-value"', svg)

    def test_missing_map_entry_falls_back_to_the_raw_slug(self):
        # A caller with no map (or a map missing this particular visual)
        # degrades to the pre-existing raw-slug behavior rather than erroring.
        page = _page([Visual(id="v1", type="card", title="Sale Value", x=0, y=0, z=0,
                             width=90, height=70, fields=["Sales.Sale_Value"])])
        svg = render_wireframe(page, visual_anchor_map={})
        self.assertIn('href="#visual-it-spend-trend-sale-value"', svg)

    def test_no_map_argument_at_all_still_works(self):
        page = _page([Visual(id="v1", type="card", title="Sale Value", x=0, y=0, z=0,
                             width=90, height=70, fields=["Sales.Sale_Value"])])
        svg = render_wireframe(page)  # no visual_anchor_map kwarg
        self.assertIn('href="#visual-it-spend-trend-sale-value"', svg)


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
