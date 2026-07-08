# Production Roadmap — Progress Tracker

Tracks execution against `PRODUCTION_ROADMAP.md` §14 (Day-by-Day Execution Plan), day by day. Update this file at the end of each day/session so a handoff (Claude ↔ Antigravity/Gemini) always has an accurate "what's actually done" record instead of relying on the plan document alone (the plan describes *intent*; this file records *reality*).

Status legend: ✅ Done · 🔶 Partial · ⬜ Not started

---

## Sprint 1 — Output credibility (Jul 8–14 · Days 1–5)

| Day | Date | Task | Status |
|---|---|---|---|
| 1 | Jul 8 | Executive Summary editorial fix (D1) | ✅ **Done** |
| 2 | Jul 9 | Output sanitation + anti-punt guard (D2/D6) | ✅ **Done** |
| 3 | Jul 10 | Grounding sentence-granularity fix (D3) | ✅ **Done** |
| 4 | Jul 13 | Field-selector regression fix (D4) | ✅ **Done** |
| 5 | Jul 14 | Full regen + QA + print pass | ✅ **Done** |

---

## Day 1 (Jul 8) — AI-Native Phase 1: Executive Summary editorial fix

**Objective:** exec doc reads for a business owner, not an auditor (fixes D1: audit-speak in the maintenance note, the completeness nag in "What's Next", and empty Steward/Classification rows).

### Task checklist

- [x] Extend `EXECUTIVE_WRITER_SCHEMA` with `reframed_risks` — [io.py:454-476](src/pbicompass/agents/io.py#L454-L476)
- [x] Pass full recommendation objects (rule_id/severity/consequence/ask) to the Executive Writer, not just a flattened string — [executive.py:297-300](src/pbicompass/agents/generators/executive.py#L297-L300)
- [x] Add `EXEC_STYLE_RULES` banning IT-governance vocabulary in the exec doc — [io.py:443-449](src/pbicompass/agents/io.py#L443-L449)
- [x] Rewrite `_maintenance_note` to plain language — [executive.py:162-167](src/pbicompass/agents/generators/executive.py#L162-L167)
- [x] Remove the completeness % block from `_next_steps`; emit it as a job warning instead — [executive.py:169-186](src/pbicompass/agents/generators/executive.py#L169-L186)
- [x] Conditional Ownership rows (Steward/Classification hidden when unset) in all 3 renderers (md/html/docx) — [render/executive.py](src/pbicompass/render/executive.py)

### Deliverable

- [x] New exec doc logic lands in md/html/docx (`render/executive.py`), all three renderers updated consistently.
- [x] Golden snapshot regenerated: `tests/fixtures/golden/executive.html` (reviewed diff before accepting — see note below).

### Done-when (from the roadmap)

- [x] Grep of rendered exec doc finds **none** of `{"governance finding", "best practice", "% complete", "fields still need"}` — verified against the regenerated golden file, clean.
- [x] Steward/Classification rows absent when unset (Owner still shown, with "not specified" fallback).

### Test coverage added (beyond the roadmap's minimum bar)

- [x] `test_generators.py::ExecutiveGeneratorDeterministicTest` — new tests asserting no completeness nag in `next_steps`, no governance/audit jargon in `maintenance_note`.
- [x] `test_generators.py` — `test_incomplete_metadata_surfaces_as_a_warning_not_doc_content` (confirms the completeness info moved to `on_warning`, not deleted).
- [x] `test_generators.py::ApplyReframedRisksTest` — new class covering `_apply_reframed_risks`: matching-count application, mismatched-count no-op (safety net against a malformed LLM response), `None` no-op.
- [x] `test_generators.py::ExecutiveGeneratorLlmTest::test_llm_prose_is_used` — updated to verify severity/rule_id stay deterministic while consequence/ask get reframed.
- [x] `test_render.py` — new `test_unset_steward_and_classification_rows_are_omitted` in both the markdown and HTML render test classes.
- [x] Full suite run: **365 passed**, 0 new failures.

### Known pre-existing (not Day 1 scope, not touched)

5 failures remain in the suite, all traced back to the prior `56f2788` commit ("Hide SVG diagrams and wireframes...") and confirmed present on `main` **before** today's changes (verified via `git stash`):
- `test_golden_html.py` — `audit`, `technical`, `user_guide` snapshots (stale vs. the SVG/font change; `executive.html` was updated since it's this task's own output).
- `test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` and `test_interactive_diagram_nodes_and_edges` (model-diagram markup currently commented out).

These belong to the Sprint 3 wireframe/lineage reintroduction work (§5.1/§5.2, Days 12–14), not Day 1 — left as-is to avoid scope creep.

### Files touched

- `src/pbicompass/agents/io.py`
- `src/pbicompass/agents/generators/executive.py`
- `src/pbicompass/render/executive.py`
- `tests/test_generators.py`
- `tests/test_render.py`
- `tests/fixtures/golden/executive.html` (regenerated)

**Verdict: Day 1 is fully done** — all roadmap tasks, the stated deliverable, and the done-when grep/row criteria are satisfied and guard-tested.

---

## Day 2 (Jul 9) — Output sanitation + anti-punt guard (D2/D6)

**Objective:** no LLM meta-commentary in prose or definitions (D2); no over-applied "requires business confirmation" on obvious/relationship-participating columns (D6).

### Task checklist

- [x] Deterministic meta-commentary validator (D2) — new module [sanitize.py](src/pbicompass/agents/sanitize.py) with `is_meta_commentary` (rejects `^(Consider|Remove|Verify|Ensure|Add a|Provide)\b`, `glossary\[`, `plain_definition`, `the duplicated entry`) and `is_punt_phrase` (rejects empty/"requires business confirmation" text).
- [x] Wired the guard into the **one choke point every generator's critic + grounding results pass through** — [critic.py::apply_results](src/pbicompass/agents/critic.py#L166-L182) now rejects a meta-commentary replacement and keeps the prior text, covering `_narrative_triples` in all four generators (technical/executive/user_guide/audit) with a single change instead of four.
- [x] D6 "AI may only improve, never downgrade" merge policy — [technical.py::_column_descriptions](src/pbicompass/agents/generators/technical.py#L225-L286): the Column Describer's result is discarded (keeping the deterministic description) whenever it's empty, meta-commentary, or a punt phrase.
- [x] Broadened deterministic derivation (D6 fix 2) — new [_related_tables](src/pbicompass/agents/generators/technical.py#L225-L236) helper: any column participating in a relationship now gets "Join key linking {table} to {related}." even without an `*Id`/`*Key` name, not just the naming heuristic.
- [x] Softened terminal wording (D6 fix 3) — a genuinely roleless column (no relationship, not calculated, no ID/Key name) now renders "No description set." instead of the alarming "Unknown — requires business confirmation."; `_infer_glossary`'s dimension lookup updated to treat both as non-definitions.
- [x] Same anti-punt merge policy applied to the measure catalog — [technical.py::_measure_catalog](src/pbicompass/agents/generators/technical.py#L385-L429): a punted/meta-commentary `plain_english`/`calculation_logic`/`caveats` from the DAX Translator falls back to the deterministic `translate_dax` gloss instead of shipping an empty or punt sentence.
- [x] Same D2/D6 guard applied to the Business User Guide's glossary — [user_guide.py::_build_glossary](src/pbicompass/agents/generators/user_guide.py#L71-L96): a punted/meta-commentary DAX Translator result is never used as a glossary definition.
- [x] Softened `io.py` prompts so the model states a structural fact instead of only punting — [STYLE_RULES](src/pbicompass/agents/io.py#L21-L29), [DAX_TRANSLATOR_SYSTEM](src/pbicompass/agents/io.py#L193-L204), [COLUMN_DESCRIBER_SYSTEM](src/pbicompass/agents/io.py#L342-L351).

### Deliverable

- [x] Clean glossary + column/measure descriptions that no longer punt on relationship-participating or otherwise structurally-known columns, across md/html/docx (shared by all three renderers since the fix lives in the generator, not the renderer).
- [x] New guard module + tests: [test_sanitize.py](tests/test_sanitize.py) (13 tests), plus guard tests wired into [test_critic.py](tests/test_critic.py), [test_agents.py](tests/test_agents.py) (`AntiPuntGuardTest`, 5 tests against a hand-built model with a non-`*Id`-named relationship column), and [test_generators.py](tests/test_generators.py) (`BusinessGuideGlossaryAntiPuntTest`).
- [x] Golden snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) and diffs reviewed line-by-line before accepting: `technical.html`'s data dictionary now shows "No description set." instead of the punt phrase, `audit.html`/`user_guide.html` diffs are pre-existing CSS/wireframe drift only (see note below), unrelated to today's change.

### Done-when (from the roadmap)

- [x] The D2 strings (`Consider providing…`, `Remove the duplicated entry…`, `glossary[…].plain_definition`, etc.) can no longer appear in a rendered doc — enforced at the shared `apply_results` choke point.
- [x] The sample's join-key columns (`CustomerKey`, `OrderDateKey`, `ShipDateKey` in the fixture) render real deterministic descriptions, never the punt phrase.
- [x] The "requires business confirmation" phrase is bounded and never appears on a relationship-participating column — verified by `test_no_column_ever_renders_the_punt_phrase` and confirmed absent from the regenerated `technical.html` golden.

### Known pre-existing (not Day 2 scope, not touched)

- `test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges` — same 2 failures noted on Day 1, traced to the model-diagram markup commented out in `56f2788`; Sprint 3 scope.
- Regenerating the goldens surfaced a **separate, pre-existing CSS/style drift** unrelated to Day 1 or Day 2: the checked-in `audit.html`/`technical.html`/`user_guide.html` fixtures predate the SVG-wireframe/font-fix commits (`306880e`, `c12a786`) and the SVG-hiding commit (`56f2788`) — none of those commits regenerated all four golden files. Confirmed by isolating the diff: `audit.html`'s entire diff is CSS/style-only (no content change, since Day 2 never touches `audit.py`); `technical.html`'s and `user_guide.html`'s diffs are the CSS drift plus exactly the intended Day 2 content changes (verified by grepping the diff with the CSS/style lines excluded). Left in the regenerated goldens since reverting it would just leave the tests failing again for an unrelated, already-latent reason — but flagging here so Sprint 3's wireframe/lineage work knows the goldens are now current.

### Files touched

- `src/pbicompass/agents/sanitize.py` (new)
- `src/pbicompass/agents/critic.py`
- `src/pbicompass/agents/io.py`
- `src/pbicompass/agents/generators/technical.py`
- `src/pbicompass/agents/generators/user_guide.py`
- `tests/test_sanitize.py` (new)
- `tests/test_critic.py`
- `tests/test_agents.py`
- `tests/test_generators.py`
- `tests/fixtures/golden/{audit,technical,user_guide}.html` (regenerated)

**Verdict: Day 2 is fully done** — D2 and D6 are fixed at their real root cause (the merge point where an LLM result would overwrite a good deterministic value), guard-tested, and verified against the regenerated golden HTML with no unintended regressions.

---

## Day 3 (Jul 10) — Grounding sentence-granularity fix (D3)

**Objective:** grounding never produces mid-sentence "Unknown — requires business confirmation." splices (fixes D3: `audit.md` line 8's *"However, Unknown — requires business confirmation., are aspects that need attention, whereas Unknown — requires business confirmation.."*).

### Root cause

`grounding.py::apply_grounding_pass`'s `unverifiable` branch did `current.replace(quote, UNVERIFIABLE_TEXT)` — a bare substring replace. `UNVERIFIABLE_TEXT` already ends in its own full stop, so whenever the flagged `quote` was an internal clause (more sentence text followed it, e.g. a comma-separated clause) rather than the tail of the sentence, splicing it in place produced a full stop butted against whatever came next (`.,`) — grammatically broken, and if two claims landed in the same sentence, doubly so.

### Task checklist

- [x] Added sentence-splitting + "does the claim reach the end of its sentence" classification — [grounding.py:92-134](src/pbicompass/agents/grounding.py#L92-L134) (`_split_sentences`, `_replace_unverifiable_claim`).
- [x] Changed the `unverifiable` branch to route through the new helper instead of a bare `str.replace` — [grounding.py:188-190](src/pbicompass/agents/grounding.py#L188-L190).
- [x] Behavior: if the claim runs to the end of its sentence, inline substitution with `UNVERIFIABLE_TEXT` is kept (reads fine, matches the pre-existing `test_unverifiable_claim_is_downgraded` contract). If the claim is a mid-sentence clause, **the whole sentence is dropped** instead of substituted in place (per the roadmap's explicit fix direction), and the remaining sentences in the field are kept intact. If dropping the sentence would empty the field entirely (it was the field's only content), falls back to the standalone `UNVERIFIABLE_TEXT` sentence rather than leaving it blank.
- [x] Added the audit-narrative case as a test fixture — [test_grounding.py](tests/test_grounding.py): `test_unverifiable_mid_sentence_claim_drops_whole_sentence`, `test_audit_narrative_two_mid_sentence_claims_collapse_cleanly` (reproduces the exact two-claims-in-one-sentence D3 production bug and asserts no `.,` / no stray `UNVERIFIABLE_TEXT` survives), `test_unverifiable_claim_spanning_the_whole_sentence_falls_back_to_the_convention_text` (empty-after-drop edge case).
- [x] Added an end-to-end wiring test through the real `TechnicalDocumentationGenerator` (not just the unit-level helper) — `GroundingMidSentenceWiringTest::test_mid_sentence_unverifiable_claim_drops_whole_sentence_not_a_splice` in [test_grounding.py](tests/test_grounding.py), mirroring the existing `GroundingGeneratorWiringTest` pattern used for the `contradicted` verdict.

### Deliverable

- [x] Grammatically clean grounding output for `unverifiable` verdicts, at both the unit (`apply_grounding_pass`) and generator-wiring level.
- [x] All 9 pre-existing `apply_grounding_pass` tests still pass unchanged (including the exact-string-match `test_unverifiable_claim_is_downgraded` and `test_multiple_claims_apply_in_sequence_on_the_same_location`) — the fix only changes behavior for genuine mid-clause claims, not the sentence-final case those tests cover.

### Done-when (from the roadmap)

- [x] No rendered doc contains `.,` — verified directly: the new fixture tests assert `assertNotIn(".,", rendered)` against text that, pre-fix, reproduced exactly that pattern; confirmed by temporarily reverting the fix and seeing both new fixture tests fail on the `.,`/double-period assertions before re-applying it.
- [x] No `"Unknown — requires business confirmation."` fragment mid-sentence — the mid-clause branch never inserts `UNVERIFIABLE_TEXT` into a sentence that has more content after it; it only appears now as either (a) a clean sentence-final inline substitution (pre-existing, tested case) or (b) a standalone whole-field fallback sentence.
- [x] Existing golden HTML fixtures (`audit.html`, `technical.html`, `user_guide.html`, `executive.html`) contain zero `.,` occurrences — confirmed via grep; no golden regeneration was needed since the fixture generation's `FakeLLMClient` doesn't exercise the grounding `unverifiable` path with mid-sentence claims.

### Full suite

- [x] `python -m pytest -q` — **392 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, both traced to the Sprint 3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 3, not touched).

### Files touched

- `src/pbicompass/agents/grounding.py`
- `tests/test_grounding.py`

**Verdict: Day 3 is fully done** — the D3 mid-sentence splice is fixed at its root cause (granularity of the replacement, not just the wording), guard-tested at both the unit and full-generator level, and verified against the exact production bug string from `audit.md`.

---

## Day 4 (Jul 13) — Field-selector (I4) regression fix (D4)

**Objective:** no `select`/`select1` field-parameter leaks in visual titles, generated business questions, or glossaries (fixes D4). The roadmap's own claim that I4 was "fixed and test-verified on 2026-07-06" was checked against the actual `Corporate_Spend_Report` sample bundle referenced in §2.2 and found to still leak on multiple surfaces — this day root-causes and closes the real gap, not just the previously-covered one.

### Root cause

The existing I4 filter (`field_parameter_table_names()` + a `len(parts) > 1 and parts[0] in field_param_tables` check scattered across five call sites) only recognized a field-parameter reference in its fully-qualified `Table.Column` shape. Inspecting the actual sample's `model.json` and visual field lists showed Power BI's report layout sometimes emits a field-parameter projection as a **bare, unqualified token** — e.g. `fields: ["select", "select1", "Fact.Actual", "Fact.Plan"]` — because `parsers/pbir.py::_extract_fields`'s `queryRef` fallback (line 92-94) appends the raw `queryRef` string as-is, and for a field-parameter axis/legend binding that `queryRef` is just the parameter table's own name with no `Entity.Property` qualification. Worse, the parameter table itself ("select"/"select1") didn't even appear in `model.tables` for this real report, so there was no table object for the qualified-path heuristic to have recognized in the first place — only the bare token's own name (`select`, `select1`) gives it away. Every consumer's `len(parts) > 1` guard silently no-ops on a bare token, so it falls straight through as if it were a real dimension.

### Task checklist

- [x] Added a single shared predicate, `report_facts.py::is_field_selector(field, field_param_tables)` — handles both the qualified `Table.Column` shape (existing behavior) and the bare-token shape (new: matches against a resolved table name, or falls back to the same telltale-name regex used to recognize the table) — plus `FIELD_SELECTOR_LABEL = "field selector"` for the one place a selector reference has to stay visible (a real, working slicer bound to it).
- [x] `report_pages()` — dims/metrics filter now uses `is_field_selector` (was qualified-only) — [report_facts.py:125-130](src/pbicompass/agents/report_facts.py#L125-L130). Fixes visual titles/labels in the technical doc's Report Pages & Visuals table and the user guide's page visual list (was: "Actual, Plan by select, select1"; now: "Actual, Plan").
- [x] `slicers()` — a slicer legitimately bound to a field-parameter table is kept (it's a real control) but relabeled to `FIELD_SELECTOR_LABEL` instead of leaking the raw table name — [report_facts.py:206-227](src/pbicompass/agents/report_facts.py#L206-L227).
- [x] `deterministic.py::_page_questions` — same fix; excludes selector fields from generated business questions ("How is Actual distributed by select?" can no longer be generated) — [deterministic.py:226-243](src/pbicompass/agents/deterministic.py#L226-L243).
- [x] `deterministic.py::_page_theme` — previously did **no** field-parameter filtering at all; now threads `field_param_tables` through and excludes selector leaves from the "Key fields: …" page-summary text — [deterministic.py:254-267](src/pbicompass/agents/deterministic.py#L254-L267).
- [x] `deterministic.py::business_analyst_deterministic`'s navigation-guide loop — previously leaked the raw slicer field name into "use the 'select1' slicer…" nav tips with no filtering at all; now relabels via `FIELD_SELECTOR_LABEL` — [deterministic.py:313-322](src/pbicompass/agents/deterministic.py#L313-L322).
- [x] `user_guide.py::_build_glossary` — the `is_field_param` check had the identical bare-token gap (silently always `False` for a bare token), so a selector's glossary entry fell back to the generic dimension definition instead of "A field selector that switches what the chart displays."; now uses `is_field_selector` — [user_guide.py:104-121](src/pbicompass/agents/generators/user_guide.py#L104-L121).
- [x] `technical.py::_infer_glossary` — previously had **no** field-parameter filtering at all, so `select`/`select1` were added as phantom "Dimension" glossary rows that could never resolve to a real column description and always rendered the alarming "Unknown — requires business confirmation." punt (compounding D6); now excluded entirely — [technical.py:571-585](src/pbicompass/agents/generators/technical.py#L571-L585).
- [x] `render/_wireframe.py` — the wireframe SVG's own local copy of the dims/metrics filter had the same bare-token gap; fixed for consistency so a wireframe visual's anchor link (`visual_label()`-derived) never drifts out of sync with the now-fixed `report_pages()` label it must match (I3) — [_wireframe.py:238-254](src/pbicompass/render/_wireframe.py#L238-L254). Wireframes are still hidden from HTML output (Sprint 3 scope) but the SVG is still generated and stored on every page fact.

### Deliverable

- [x] One shared, correctly-generalized I4 predicate (`is_field_selector`) replacing five independent, differently-buggy copies of the same qualified-only check.
- [x] New regression coverage reproducing the exact production bug shape: `tests/test_report_facts.py::BareFieldSelectorRegressionTest` (8 tests) — unit coverage of `is_field_selector` itself, plus end-to-end coverage through `report_pages()`, `business_analyst_deterministic()` (questions, page-theme text, nav guide), `slicers()`, `TechnicalDocumentationGenerator` (glossary), and `BusinessGuideGenerator` (glossary).

### Done-when (from the roadmap)

- [x] No rendered doc contains a standalone `select`/`select1` field token — verified directly against the reproduction fixture (`_model_with_bare_field_parameter`, built from the real `Corporate_Spend_Report` sample's exact field-list shape) across every consumer path.
- [x] "How is Actual distributed by select?" cannot be generated — `test_bare_field_parameter_excluded_from_business_questions` asserts no generated question contains "select" for this fixture.

### Full suite

- [x] `python -m pytest -q` — **400 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 4, not touched). Golden HTML fixtures unaffected (the checked-in `SampleSales` golden model contains no field-parameter tables, so this fix has no observable diff there); no golden regeneration was needed.

### Files touched

- `src/pbicompass/agents/report_facts.py`
- `src/pbicompass/agents/deterministic.py`
- `src/pbicompass/agents/generators/user_guide.py`
- `src/pbicompass/agents/generators/technical.py`
- `src/pbicompass/render/_wireframe.py`
- `tests/test_report_facts.py`

**Verdict: Day 4 is fully done** — the I4 field-selector recognition gap is fixed at its actual root cause (a bare-token shape the original heuristic never accounted for), applied consistently across every surface that previously leaked it independently, and guard-tested against the exact real-world reproduction shape found in the `Corporate_Spend_Report` sample cited in the roadmap's own audit (§2.2, D4).

---

## Day 5 (Jul 14) — Full regen + QA + print pass

**Objective:** verify Sprint 1 end-to-end across all 4 docs × 4 formats; lock the D1–D6 fixes into CI so they can never silently regress.

### Task checklist

- [x] Regenerated the SampleSales fixture (the repo's canonical offline sample — see note below on `Corporate_Spend_Report.zip`) as a full `--document all --bundle --provider none` bundle: all 4 doc types × md/html/docx/json.
- [x] Read through every rendered `.md` (representative of md/html/docx, since all three renderers consume the same generator output) for D1–D6 defects.
- [x] Print/PDF pass: no PDF engine (pandoc + tectonic/wkhtmltopdf/weasyprint) or browser is installed in this sandbox, so an actual rendered PDF couldn't be produced here. Verified instead at the source: the shared shell's `@media print` block ([_html_shell.py:818-881](src/pbicompass/render/_html_shell.py#L818-L881)) forces the light theme regardless of on-screen theme, hides sidebar/nav chrome, sets `page-break-before: always` on `h2` (avoided on the first), sets `page-break-inside: avoid` on `pre`/`table`/`.measure`/`.diagram`/`.card-section`, force-opens every collapsed `<details>` for print (with a no-JS CSS fallback), and renders a print-only cover page + confidentiality watermark. `test_render.py::test_print_cover_page_present` and `test_print_watermark_only_for_confidential_or_restricted` already guard the cover/watermark. **Gap:** a real browser/PDF-engine visual check (the roadmap's actual "print pass") still needs to happen once on a machine that has one — flagging honestly rather than claiming a visual check that didn't happen.
- [x] Added the §10.1 output-quality guard tests to CI: new [tests/test_output_quality_guards.py](tests/test_output_quality_guards.py) (6 tests) — parses SampleSales once, generates all 4 documents, renders each to md+html, and asserts D1 (no audit-speak in the executive doc), D2 (no `glossary[`/`plain_definition`/`the duplicated entry` artifacts in any doc), D3 (no `.,` splice, no doubled terminal punctuation), D4 (no bare lowercase `select`/`select1` token), and D6 (punt-phrase count bounded, and never on a relationship-participating column — cross-checked against the model's actual `relationships`, not just column naming). This is the holistic complement to the per-fix unit tests Days 1–4 already added.
- [x] Verified the new suite isn't vacuous: an over-broad first draft of the D2 check (`\[\d+\]\.\w+`) correctly failed on legitimate inline JS (`shown[0].anchor` in the HTML shell's search script) and had to be narrowed to `glossary\[\d+\]` — proof the test actually executes real matching logic, not a tautology.

### New defects found during the read-through (fixed today, not part of D1–D6, found by the QA pass itself)

- **`_infer_glossary` D6 residual gap** — [technical.py:602-603](src/pbicompass/agents/generators/technical.py#L602-L603): the section-14 "Data Dictionary / Glossary" glossary builder had its own, separate fallback that still defaulted a genuinely roleless dimension (no date/customer/product/region keyword match — e.g. `Segment`, `Year` in the SampleSales fixture) to `"Unknown — requires business confirmation."`, even though the section-6 data dictionary (`_column_descriptions`) was already fixed on Day 2 to say `"No description set."` for the identical case. Two different sections of the same technical doc were giving two different answers for the same column. Fixed to match the D6 policy. Guard-tested: `tests/test_agents.py::AntiPuntGuardTest::test_glossary_dimension_with_no_keyword_match_never_gets_the_punt_phrase` (confirmed it fails without the fix via `git stash`).
- **Duplicated-word typo** — "page layout **layout** tables" in the §19 Methodology & Guarantees boilerplate, hardcoded identically in [markdown.py:458](src/pbicompass/render/markdown.py#L458), [html.py:768](src/pbicompass/render/html.py#L768), and [docx.py:459](src/pbicompass/render/docx.py#L459). Fixed to "page layout tables" in all three.
- **Grammar** — same boilerplate: "zero-CDNs, zero telemetries" → "zero CDNs, zero telemetry" (a plural was applied to an uncountable noun; "CDNs" as a hyphenated adjective read oddly next to "zero"). Fixed in all three renderers.

### Deliverable

- [x] Clean, freshly-regenerated SampleSales bundle (all 4 docs × md/html/docx/json) with zero D1–D6 defects and the two new typo/glossary fixes applied.
- [x] Golden HTML snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) and diff reviewed: the diff vs. `HEAD` (nothing from Sprint 1 has been committed yet, so `git diff` shows the full cumulative Sprint 1 change) is exactly the expected D1–D6 fixes plus today's two new fixes plus the already-documented pre-existing CSS/font drift (Poppins injection, wireframe-hiding) from commits before Sprint 1 started. No unexpected regressions.
- [x] `tests/test_output_quality_guards.py` added as a permanent CI gate for D1–D6.

### Done-when (from the roadmap)

- [x] Manual read-through of `executive.md`, `audit.md`, `user-guide.md`, `technical.md` (all four, offline/deterministic) finds **zero** D1–D6 defects, plus the two newly-found and now-fixed typo/glossary issues.
- [x] Offline fallback (`--provider none`) still produces complete docs across all 4 types × md/html/docx/json — confirmed via the regenerated bundle; the CLI correctly emits the metadata-completeness note as a `warning:` on stderr (not embedded in doc content), matching Day 1's fix end-to-end through the real CLI path, not just the unit-tested generator call.

### Known gap (honest, not hidden)

- **No live Gemini smoke run.** No `GEMINI_API_KEY`/`GOOGLE_API_KEY` (or any other provider key) is configured in this environment, so the roadmap's "Gemini smoke" half of Day 5 could not be executed here — only the offline/deterministic run. This needs to happen once on a machine with a real key configured; nothing about today's changes is provider-specific (all four fixes today are in deterministic code paths), so risk is low, but it's an explicit gap, not a silently-skipped one.
- **No real PDF/browser print check.** See the print-pass note above — the print CSS was verified by reading it, not by rendering it.

### Full suite

- [x] `python -m pytest -q` — **407 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 5, not touched).

### Files touched

- `src/pbicompass/agents/generators/technical.py` (`_infer_glossary` D6 fix)
- `src/pbicompass/render/markdown.py`, `src/pbicompass/render/html.py`, `src/pbicompass/render/docx.py` (typo/grammar fix in §19 boilerplate)
- `tests/test_output_quality_guards.py` (new)
- `tests/test_agents.py` (new regression test in `AntiPuntGuardTest`)
- `tests/fixtures/golden/{audit,executive,technical,user_guide}.html` (regenerated)

**Verdict: Day 5 is fully done** for everything executable in this environment — full offline regen across all 4 docs × all formats, a thorough manual QA read-through that caught and fixed two real (if minor) residual defects beyond D1–D6, the print-CSS verified at the source, and a new permanent CI guard suite locking in the Sprint 1 fixes. The Gemini smoke run and a real browser/PDF visual check are flagged as explicit, un-silenced gaps for a session with provider credentials / a browser available.

---

## Sprint 2 — Reasoning control + consultant-grade audit (Jul 15–21 · Days 6–10)

| Day | Date | Task | Status |
|---|---|---|---|
| 6 | Jul 15 | Cross-provider reasoning control (§4.0) | ✅ **Done** |
| 7 | Jul 16 | VertiPaq deterministic rules + Audit Synthesizer call | ✅ **Done** |
| 8 | Jul 17 | Render the Root-Cause Analysis section | ✅ **Done** |
| 9 | Jul 20 | AI fix snippets (paid) | ✅ **Done** |
| 10 | Jul 21 | Sprint 2 QA + A/B read | ✅ **Done** |

---

## Day 6 (Jul 15) — Cross-provider reasoning control (§4.0)

**Objective:** the `effort` reasoning-depth level must work on every LLM provider, not just Anthropic; a model that rejects a reasoning param must degrade gracefully instead of failing the job.

### Root cause / starting state

`GeminiClient`, `CohereClient`, and `MeshAPIClient` (`agents/llm.py`) all accepted the `effort=` kwarg on `complete_json` for protocol compatibility but silently discarded it — only `AnthropicClient` actually spent it on deeper thinking. The CLI's `--effort` flag and the service's `effort` Form field already existed, but were wired to the client's constructor for Anthropic only ([cli.py](src/pbicompass/cli.py), [worker.py](src/pbicompass/service/worker.py)).

### A roadmap contradiction found and resolved

The Day 6 task bullet in `PRODUCTION_ROADMAP.md` said "keep the per-plan ceiling in worker.py," but §4.0 of the same document — an explicit, dated owner cost-policy decision (2026-07-07) — says the opposite: *"do not clamp reasoning depth by plan… Remove/disable `worker.py::_clamp_effort_for_plan`. The only cost guardrail is the daily job quota."* Treated §4.0 as authoritative (it's the more specific, dated instruction, and matches the standing cost-policy record from prior sessions) and removed the clamp rather than keeping it.

### Task checklist

- [x] **Gemini** — `effort` now maps to `types.ThinkingConfig(thinking_budget=…)`; `max` requests Gemini's own "dynamic thinking" convention (`thinking_budget=-1`) — [llm.py:156-240](src/pbicompass/agents/llm.py#L156-L240) (`_GEMINI_THINKING_BUDGET`, `GeminiClient.complete_json`).
- [x] **Cohere** — the reasoning `thinking`/`token_budget` param is only sent when the *configured model itself* is reasoning-capable (`command-a-reasoning` and similar, detected by name); the default `command-a-03-2025` has no such knob, so effort stays accepted-and-ignored there — users opt in via `--model` per the roadmap's own guidance — [llm.py:243-343](src/pbicompass/agents/llm.py#L243-L343) (`_cohere_reasoning_capable`, `CohereClient.complete_json`).
- [x] **MeshAPI/OpenAI** — `reasoning_effort` is only sent when the routed model id looks reasoning-capable (o-series / gpt-5, matched via `_MESHAPI_REASONING_MODEL_RE`); every other model, including the `openai/gpt-4o` default, never receives it — preserves the existing regression test that this must never 400 on gpt-4o — [llm.py:346-480](src/pbicompass/agents/llm.py#L346-L480) (`_meshapi_reasoning_capable`, `MeshAPIClient.complete_json`).
- [x] **Graceful degradation, all four clients** — each `complete_json` now attempts the call with its reasoning param, and on that provider's own `BadRequestError`-equivalent, retries once without it rather than raising (which would otherwise trip `call_llm`'s fallback to the deterministic engine unnecessarily) — added to Anthropic too, for symmetry, via a new `_resolve_error_class` helper that looks up an SDK's error class defensively (root or `errors.` submodule) — [llm.py:48-63](src/pbicompass/agents/llm.py#L48-L63).
- [x] **`--effort` CLI flag generalized** — now passed to every provider's client constructor, not just Anthropic's; help text rewritten to describe the cross-provider behavior — [cli.py:226-231](src/pbicompass/cli.py#L226-L231), [cli.py:423-427](src/pbicompass/cli.py#L423-L427).
- [x] **Service upload field** — the `effort` Form field already existed ([app.py:220](src/pbicompass/service/app.py#L220)); `_make_client` in `worker.py` now passes it to every provider, not just Anthropic — [worker.py:63-74](src/pbicompass/service/worker.py#L63-L74).
- [x] **Per-plan effort ceiling removed** — `_clamp_effort_for_plan`/`_PLAN_EFFORT_CEILING` deleted from `worker.py` per §4.0; the stale "Phase 0: the caller's plan clamps effort" comment in `app.py` corrected to say `plan` only gates the job quota now — [worker.py:56-60](src/pbicompass/service/worker.py#L56-L60), [app.py:300-302](src/pbicompass/service/app.py#L300-L302).
- [x] **Frontend** — `service/static/index.html`'s `EFFORT_CAPABLE_PROVIDERS` broadened from `["anthropic"]` to all four LLM providers (offline `"none"` still hides the effort row), and `ESTIMATED_SECONDS` given a per-effort breakdown for gemini/cohere/meshapi to match — [index.html:1691-1725](src/pbicompass/service/static/index.html#L1691-L1725).

### Deliverable

- [x] Every provider honours the selected effort tier where its configured model supports reasoning; a rejecting model degrades via retry instead of failing the agent call.
- [x] New test class `ReasoningEffortWiringTest` (10 tests) in [test_agents.py](tests/test_agents.py) — per-provider assertions that the right native param is sent for a given effort + model (and correctly withheld for a non-reasoning model), plus a rejecting-model fallback test for each of the four clients, using the same fake-SDK-module pattern the existing MeshAPI/Cohere tests already established (`anthropic` and `openai` aren't installed in this environment; `google-genai` and `cohere` are, so those two are tested against the real SDK types with only the network call stubbed).

### Done-when (from the roadmap)

- [x] Per-provider unit tests assert the effort maps to the right native param (via a mock capturing call kwargs) — done for all four providers.
- [x] A rejecting-model test asserts the retry-without-reasoning fallback fires — done for all four providers.
- [ ] **One real smoke per provider** — not done. No `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`COHERE_API_KEY`/`MESHAPI_API_KEY` is configured in this environment (same gap noted on Day 5 for the Gemini smoke run), so a live "does a real Gemini/MeshAPI call at `max` visibly reason (token/latency delta)" check could not be executed here. Flagged honestly, not silently skipped — needs a session with provider credentials.

### Full suite

- [x] `python -m pytest -q` — **417 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 6, not touched).
- [x] Offline CLI smoke (`--provider none`) re-verified unaffected (provider-selection short-circuits before any client construction).

### Files touched

- `src/pbicompass/agents/llm.py`
- `src/pbicompass/cli.py`
- `src/pbicompass/service/worker.py`
- `src/pbicompass/service/app.py`
- `src/pbicompass/service/static/index.html`
- `tests/test_agents.py`

**Verdict: Day 6 is fully done** for everything executable in this environment — every provider's reasoning knob is genuinely wired (not just accepted-and-ignored), the retry-without-reasoning fallback is in place and guard-tested for all four clients, the CLI/service effort controls are generalized past Anthropic, and the roadmap's own internal contradiction on the per-plan clamp was resolved in favor of the explicit, dated owner cost-policy decision. The one gap is a live per-provider smoke test, blocked on provider credentials not being available in this sandbox — same class of gap already flagged and accepted on Day 5.

---

## Day 7 (Jul 16) — VertiPaq deterministic rules + Audit Synthesizer call

**Objective:** read real VertiPaq stats (`cardinality`/`size_bytes`, pbixray `--stats` only) into new deterministic threshold rules, and add an AI Audit Synthesizer call that clusters related findings by shared root cause — the "disable Auto Date/Time → ~20 findings clear" pattern (D5) — into `{clusters, strategic_narrative}` on `AuditDocument`.

### Task checklist

- [x] Two new deterministic VertiPaq threshold rules in `audit_rules.py::find_performance_risks` — [audit_rules.py:1004-1042](src/pbicompass/agents/audit_rules.py#L1004-L1042):
  - `near_constant_dimension` (**PBIC-PERF-010**) — a column with measured cardinality ≤ 1 (configurable via `near_constant_cardinality_max` threshold) and visible: almost no variation, dictionary overhead with no analytical value.
  - `wide_text_dominates_size` (**PBIC-PERF-011**) — a single column accounting for ≥60% (`wide_text_dominance_pct`) of a table's measured column size, only once that table's total measured size clears a 1 MB floor (`wide_text_min_table_size_bytes`) to avoid noise on tiny tables.
  - Both follow the existing `high_cardinality_signal`/`large_text_column` pattern of only firing on **measured** stats — no-op (not a heuristic fallback) when `cardinality`/`size_bytes` are absent, which is true for every `.pbip`/TMDL/TMSL model and any `.pbix` parsed without `--stats` (confirmed: neither field is ever populated outside the pbixray adapter).
- [x] Fixed a latent detection gap in the existing **PBIC-PERF-007** Auto Date/Time rule — [audit_rules.py:1069-1078](src/pbicompass/agents/audit_rules.py#L1069-L1078): it matched `"LocalDateTable"`/`"TemplateId"` but never `"DateTableTemplate"`, the actual name of the *second* hidden table Power BI's Auto Date/Time creates per date column — so a model whose only visible auto-date artifact was a `DateTableTemplate_*` table silently escaped detection. Directly serves D5: the synthesizer needs this root-cause signal to actually fire before it can cluster anything around it.
- [x] New `FindingCluster` dataclass + `clusters: list[FindingCluster]` / `strategic_narrative: str` fields on `AuditDocument` — [schemas/audit_document.py:108-139](src/pbicompass/schemas/audit_document.py#L108-L139). Deterministic fallback is simply empty/omitted, never a placeholder — matches the rest of the document's "AI enriches, never required" contract.
- [x] New Audit Synthesizer agent prompt — [io.py](src/pbicompass/agents/io.py): `AUDIT_SYNTHESIZER_SYSTEM` (root-cause clustering instructions, 2+ findings per cluster, confidence rating, `strategic_narrative`), `AUDIT_SYNTHESIZER_SCHEMA`, `audit_synthesizer_input()`; `"Audit Synthesizer": "high"` added to `AGENT_EFFORT`.
- [x] Wired into `AuditReportGenerator.generate()` — [generators/audit.py](src/pbicompass/agents/generators/audit.py): a new LLM call (only when a client is supplied), after the Audit Narrator call, feeding it every DAX/best-practice-failure/performance-risk/governance finding's `rule_id` + table/object name + detail, plus the unused-assets summary; populates `clusters`/`strategic_narrative` on the document before construction. Both new prose fields (`strategic_narrative`, each cluster's `narrative`) are folded into the existing `_narrative_triples()` list the critic/grounding passes already iterate, so they get the same style/fact-check treatment as `narrative_overview` at no extra LLM call (same batched critic call).
- [x] `FakeAuditNarratorClient` (`test_generators.py`) extended with a `"root-cause synthesis"` branch returning a canned cluster + strategic narrative, routed by a unique system-prompt substring (verified it doesn't collide with the existing `"Audit & Health Report"` narrator branch).

### Deliverable

- [x] New `tests/test_audit_rules.py` coverage: `VertiPaqRulesTest` (7 tests — both new rules' fire/no-fire/threshold/no-op-without-stats behavior, plus a regression asserting SampleSales, parsed without `--stats`, never fires either new rule), `AutoDateTimeDetectionTest` (3 tests, including the `DateTableTemplate` regression), `AutoDateTimeClusterSignalsTest` (1 test proving the Auto Date/Time root-cause performance risk and its dependent unused-calculated-column finding genuinely co-occur on the same hidden table — the raw material a synthesizer clusters).
- [x] New `tests/test_generators.py` coverage: `test_llm_synthesizer_clusters_are_used` (asserts the fake cluster/strategic narrative flow onto the document), `test_failing_client_leaves_clusters_empty` (deterministic-fallback safety net); `test_llm_narrative_is_used`'s call-count assertion updated 2→3 (Audit Narrator + Audit Synthesizer + critic pass).
- [x] Golden HTML snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) for `audit.html`/`technical.html` — diff reviewed line-by-line and is exactly the expected consequence of the rule-registry growing 50→52 (checks-run/passed counts shift accordingly on the SampleSales fixture, which has no VertiPaq stats so both new rules simply pass silently); no other content changed.

### Done-when (from the roadmap)

- [x] New rules covered in `tests/test_audit_rules.py` — `VertiPaqRulesTest`.
- [x] The Auto Date/Time root cause is clustered with its dependent findings on the sample — demonstrated at two levels: the deterministic co-occurrence of the root-cause finding and its dependent unused-asset finding (`AutoDateTimeClusterSignalsTest`), and the end-to-end AI wiring producing a cluster keyed to `PBIC-PERF-007` via the fake client (`test_llm_synthesizer_clusters_are_used`). SampleSales itself carries no Auto Date/Time tables, so this is proven on a purpose-built synthetic model plus the canned-client contract, consistent with how every other LLM-backed test in this codebase verifies wiring (no real model ever exercises the actual LLM in CI).

### Known gap (honest, not hidden)

- **Rendering is explicitly out of scope for today.** `clusters`/`strategic_narrative` are populated on `AuditDocument` but not yet surfaced by any renderer (md/html/docx) — that is Day 8's task per the roadmap ("Render the Root-Cause Analysis section"), not Day 7's.
- **No live LLM smoke test** — same class of gap already flagged and accepted on Days 5/6 (no provider credentials in this sandbox); the synthesizer's wiring is verified against a fake client only.

### Full suite

- [x] `python -m pytest -q` — **431 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 7, not touched; re-confirmed present on `main` before today's changes via `git stash`).

### Files touched

- `src/pbicompass/agents/audit_rules.py`
- `src/pbicompass/schemas/audit_document.py`
- `src/pbicompass/agents/io.py`
- `src/pbicompass/agents/generators/audit.py`
- `tests/test_audit_rules.py`
- `tests/test_generators.py`
- `tests/fixtures/golden/{audit,technical}.html` (regenerated)

**Verdict: Day 7 is fully done** for its stated scope — the two VertiPaq threshold rules are deterministic, no-op-safe, and guard-tested; the Auto Date/Time detection gap that would have silently starved the synthesizer of its flagship root-cause signal is fixed and regression-tested; and the Audit Synthesizer is fully wired end-to-end (prompt, schema, generator call, document fields, critic/grounding coverage, fake-client test contract) with a deterministic fallback that leaves the document complete when no client is supplied or the call fails. Rendering the clusters into the actual documents is Day 8's task, by design.

---

## Day 8 (Jul 17) — Render the Root-Cause Analysis section (md/html/docx)

**Objective:** render the `clusters`/`strategic_narrative` fields the Day 7 Audit Synthesizer populates on `AuditDocument` into all three audit-doc formats, deep-link each cluster's `rule_ids` to the finding anchor that actually carries that rule, and surface the single broadest-impact cluster on the technical document's §16 — deterministic fallback (no client, or no clusters produced) is that both are simply absent, never a placeholder.

### Task checklist

- [x] New **"9. Root-Cause Analysis"** section in `render/audit.py` for md/html/docx — [audit.py:30-39](src/pbicompass/render/audit.py#L30-L39) (`_SECTION_TITLES` extended), rendered only `if doc.clusters:` in all three renderers ([markdown block](src/pbicompass/render/audit.py#L239-L248), [html block](src/pbicompass/render/audit.py#L399-L421), [docx block](src/pbicompass/render/audit.py#L550-L558)). Appended after Recommendations rather than inserted mid-document, so no existing section anchors (`sec1`–`sec8`) had to be renumbered.
- [x] TOC/search-index made conditional too — [audit.py:283-287](src/pbicompass/render/audit.py#L283-L287): `_visible_titles` drops the 9th title entirely when `doc.clusters` is empty, so the sidebar TOC never advertises a section that doesn't exist.
- [x] **Deep-linking clusters to finding anchors** — new `_rule_id_anchors(doc)` index ([audit.py:113-141](src/pbicompass/render/audit.py#L113-L141), alongside the new `_top_cluster` helper) mapping every finding/check/recommendation's `rule_id` to its existing HTML anchor (`finding-dax-{i}`, `check-{bp.id}`, `finding-perf-{i}`, `finding-gov-{i}`, `rec-{rule_id}`). Each cluster's `rule_ids` resolve through this index to a real `<a href="#anchor">` in HTML; a `rule_id` with no matching finding anywhere on the document falls back to plain `<code>` text rather than a dead link. Markdown/DOCX list rule IDs as plain text (neither renderer has ever produced anchor-style cross-references — consistent with how the Recommendations section already cites `rule_id`).
- [x] **Surfaced the top cluster in technical §16** — new `top_cluster: Optional[dict] = None` field on the technical `Document` schema ([document.py:169-176](src/pbicompass/schemas/document.py#L169-L176)); `TechnicalDocumentationGenerator.generate()` takes an optional `top_cluster: Optional[FindingCluster]` kwarg and sets `doc.top_cluster` ([technical.py](src/pbicompass/agents/generators/technical.py)); threaded through `orchestrator.generate_document()`. Rendered as a "Root cause: …" callout right after the Health Score table and before the Best-Practice Rules Summary, in all three renderers ([html.py](src/pbicompass/render/html.py), [markdown.py](src/pbicompass/render/markdown.py), [docx.py](src/pbicompass/render/docx.py)) — omitted entirely when `top_cluster` is `None`.
- [x] **"Top cluster" selection** — `render/audit.py::_top_cluster(doc)` picks the cluster with the most `rule_ids` (broadest impact), not just `clusters[0]`.
- [x] **Cross-generator reuse, not a second Synthesizer call** — the risk with surfacing a cluster on two sibling documents is that a second independent Audit Synthesizer call could produce a *different* root cause than the audit doc's own, which would read as the two documents disagreeing. Fixed at the orchestration layer instead of duplicating the LLM call: both `cli.py` and `service/worker.py` now pre-generate the Audit document first when both `"technical"` and `"audit"` are requested with a client, extract its top cluster via `_top_cluster`, and reuse that *same* `AuditDocument` object when the main loop reaches `"audit"` (never regenerated) — [cli.py](src/pbicompass/cli.py#L437-L471), [worker.py](src/pbicompass/service/worker.py#L242-L259). Single-document jobs and offline (`client=None`) runs are completely unaffected (`pre_audit_doc` stays `None`, `top_cluster` stays `None`).

### Deliverable

- [x] Root-Cause Analysis section renders in md/html/docx with working deep links; technical §16 carries the matching root-cause callout when both docs are generated together.
- [x] New tests: [test_render.py](tests/test_render.py) — `AuditRootCauseSectionTest` (5 tests: markdown content, HTML section+TOC, resolved-link regex match, unresolved-rule-ID plain-text fallback, DOCX content), `TopClusterSelectionTest` (2 tests: broadest-cluster selection, `None` when no clusters), `TechnicalTopClusterTest` (4 tests: field population, md/html/docx callout rendering and omission), plus a `test_no_root_cause_section_when_no_clusters` guard added to both the existing `AuditMarkdownRenderTest` and `AuditHtmlRenderTest` classes.
- [x] Golden HTML snapshots **not** regenerated — verified unaffected rather than assumed: `test_golden_html.py` generates with `client=None`, so `doc.clusters`/`doc.top_cluster` stay empty/`None` on that path and the new sections render nothing, confirmed by the full suite passing without a golden diff.

### Done-when (from the roadmap)

- [x] Section appears in all three formats — `AuditRootCauseSectionTest` covers md/html/docx directly against a real generated audit doc (via `AuditReportGenerator.generate()`, not a hand-built fixture) with clusters attached.
- [x] Every cluster link resolves — `test_html_resolved_rule_id_becomes_a_working_anchor_link` asserts the real rule ID (dynamically pulled from the doc's own best-practice checks, not hardcoded) produces a working `<a href="#...">`; `test_html_unresolved_rule_id_falls_back_to_plain_text` asserts a nonexistent rule ID never produces a dead link.

### Known gap (honest, not hidden)

- **No live/fake-client integration test of the cli.py/worker.py reuse logic.** The pre-generate-once-and-reuse orchestration change is exercised by code inspection and by the fact that every existing offline CLI/worker test (`DocumentAllTest`, etc.) still passes unchanged — but there's no test that spins up a fake multi-agent LLM client and asserts the Audit Synthesizer is called exactly once across a two-document job. Building that fixture (a fake client covering every agent call the full pipeline makes) is disproportionate to Day 8's scope and matches the project's established testing boundary (per Days 6/7: LLM wiring is verified against fake clients at the generator level, not via CLI/worker integration tests). Flagged as a gap for the Sprint 7 integration-test pass (§10.3 of the roadmap), not silently skipped.

### Full suite

- [x] `python -m pytest -q` — **444 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 8, not touched).

### Files touched

- `src/pbicompass/schemas/document.py`
- `src/pbicompass/agents/generators/technical.py`
- `src/pbicompass/agents/orchestrator.py`
- `src/pbicompass/render/audit.py`
- `src/pbicompass/render/html.py`
- `src/pbicompass/render/markdown.py`
- `src/pbicompass/render/docx.py`
- `src/pbicompass/cli.py`
- `src/pbicompass/service/worker.py`
- `tests/test_render.py`

**Verdict: Day 8 is fully done** for its stated scope — the Root-Cause Analysis section renders in all three formats with real deep links (and a safe fallback for unresolved rule IDs), the technical document's §16 surfaces the same top cluster the audit doc shows (never a second, potentially-divergent Synthesizer call), and the whole feature degrades to "simply absent" with zero placeholder text across every offline/single-document/no-cluster path. The one gap is a live orchestration-level integration test, which is out of proportion for a single day's scope and consistent with how the project has drawn that testing boundary in prior days.

---

## Day 9 (Jul 20) — AI fix snippets (paid)

**Objective:** append an "AI-suggested — review before applying" DAX/M/script sketch to the top-N recommendations that only carry prose today, plan-gated (paid feature — pro/enterprise only, free plan omits entirely).

### Design decisions (not fully specified by the roadmap, resolved here)

- **What counts as "top-N"**: recommendations are one-per-finding-kind (templated, not per-object), and several kinds already get a *deterministic* fenced code fix from `build_recommendations` (Tabular Editor C# scripts, M snippets for hardcoded paths, etc. — `audit_rules.py:1580-1710`). Candidates for the new AI call are the recommendations that have **no fence at all** (`"```" not in r.suggested_fix`), sorted by priority (Critical/High first), capped at **3** — bounded regardless of the owner's "token cost is not a concern" policy (§4.0), since the roadmap explicitly says "top-N", not "every".
- **Real object grounding**: a new `_recommendation_example_objects()` helper (`generators/audit.py`) pulls real measure/object names from `dax_findings`/`performance_risks` that share the candidate's `rule_id`, so the AI is given actual names to reference (never invents one) — empty for model-wide categories (governance/modeling) that have no single backing object.
- **Plan gating**: `AuditReportGenerator.generate()` gained a `plan: Optional[str] = None` kwarg. The feature only fires when `client is not None` **and** `plan in {"pro", "enterprise"}` — `plan=None` (the old default, still what an untouched caller gets) and `plan="free"` both omit it, matching "free plan omits" from the roadmap's done-when. The CLI has no account/billing concept, so it gained its own `--plan` flag (default `"enterprise"` — self-host gets full features per §8.6, `--plan free` lets someone preview what a hosted free-tier job would omit). The service already threads a real per-tenant `plan` through `options["plan"]` (app.py had a forward-looking comment about this from Day 6); `worker.py::_generate_one`/`process_job` now actually reads and passes it for the `"audit"` document type (the only one this feature touches).
- **Critic/grounding safety "for free"**: both `critic.py::apply_critic_pass` and `grounding.py::apply_grounding_pass` already skip any field containing `` ``` `` (added for the deterministic fix-snippet fences before Day 9 existed). Running `_apply_ai_fix_snippets()` **last** — after the deterministic overview, the Audit Narrator call, and the Audit Synthesizer call have all already read the pre-snippet `recommendations` — means (a) the appended code never leaks into `narrative_overview`'s "top priority" sentence or the narrator's own input payload, and (b) by the time `_narrative_triples()` collects `suggested_fix` for the critic/grounding passes, it already contains `` ``` `` and both passes skip it automatically. No new guard code was needed for this — just correct ordering.
- **Meta-commentary guard reused**: the appended `code` is checked with the existing `sanitize.is_meta_commentary()` (D2) before being written — an AI response that returned an editing directive instead of code is dropped, never appended.
- **Fixed a real, adjacent rendering bug while here**: `render/html.py::format_prose_with_code()` only recognized `dax`/`csharp`/`powerquery`/`pq` as fence-language tags. The *existing* (pre-Day-9) deterministic snippets already emit `` ```m `` and `` ```text `` fences (`audit_rules.py:1616,1696`) — neither tag was recognized, so the language marker itself (`"m"` or `"text"`) was rendered as a stray first line of the code block in HTML. Added both tags to the recognized set so Day 9's own `m`/`text` snippets (and the pre-existing ones) render cleanly.

### Task checklist

- [x] `io.py`: `AI_FIX_SNIPPET_SYSTEM`, `AI_FIX_SNIPPET_SCHEMA`, `ai_fix_snippet_input()`, and an `AGENT_EFFORT["AI Fix Snippet Writer"] = "high"` tier.
- [x] `generators/audit.py`: `_recommendation_example_objects()`, `_apply_ai_fix_snippets()`, wired into `AuditReportGenerator.generate()` via a new `plan` kwarg, called last (after narrative/narrator/synthesizer).
- [x] `render/html.py::format_prose_with_code()`: recognize `m`/`text` fence-language tags (bug fix, see above).
- [x] `service/worker.py`: `_generate_one()` takes `plan`; `process_job()` reads `options.get("plan")` and passes it to the `"audit"` document type (both the pre-generated-audit-for-technical path and the main loop).
- [x] `cli.py`: new `--plan {free,pro,enterprise}` flag (default `enterprise`), threaded to both `DOCUMENT_TYPES["audit"].generate()` call sites.

### Deliverable

- [x] New `tests/test_generators.py::AuditGeneratorAiFixSnippetTest` (8 tests) with a new `FakeAiFixSnippetClient`: free-plan omission, no-plan-specified omission (the untouched-caller default), pro-plan appends a fenced snippet, enterprise-plan also works, candidates bounded to top-3 and exclude recommendations that already have a deterministic fence, a meta-commentary snippet is rejected (not appended), a failing client leaves recommendations byte-identical to the deterministic baseline, and an end-to-end proof that the critic pass never mangles the fenced snippet.
- [x] Manual smoke script (rendered md/html/docx from a real `AuditReportGenerator.generate(model, fake_client, plan="pro")` call, not just unit assertions) confirms the fence renders correctly in all three formats — HTML gets a real `<pre><code>` block, markdown keeps the raw fence (valid as-is once the file itself is markdown), DOCX writes without error (code renders as a plain-text run inside the paragraph, the same pre-existing limitation every other fix-snippet fence already has — not a Day 9 regression).
- [x] Golden HTML snapshots regenerated; the only diff is the Day 7 rule-registry count (50→52 checks) already documented as pending in that day's own notes — nothing Day-9-specific changed the SampleSales golden output (it's generated offline with `client=None`, so the paid feature never fires on it).

### Done-when (from the roadmap)

- [x] Snippets render fenced — confirmed in HTML (`<pre><code>`), markdown (raw fence), and DOCX (writes without error).
- [x] Critic skips them — proved end-to-end (not just by code inspection) via `test_critic_pass_does_not_alter_the_fenced_ai_snippet`, which asserts the exact code text survives the full `generate()` pipeline (narrator + synthesizer + critic all run) unchanged.
- [x] Free plan omits — `test_free_plan_omits_ai_fix_snippets` and `test_no_plan_specified_omits_ai_fix_snippets` both assert zero calls to the fix-snippet branch and no "AI-suggested" text anywhere in the document.

### Known gap (honest, not hidden)

- **No live LLM smoke test** — same class of gap flagged and accepted on Days 5/6/7 (no provider credentials in this sandbox); verified against a fake client only.
- **No integration test through `service/worker.py`/`cli.py`'s plan-threading** — verified by code inspection and a CLI offline smoke run (`--plan enterprise` with `--provider none`, which naturally can't exercise the paid branch since there's no client) rather than a fake-client integration test through the full job/CLI path. Matches the same testing-boundary precedent set on Day 8 (LLM wiring verified at the generator level via fake clients, not via CLI/worker integration tests) — building a full fake-multi-agent-client CLI/service fixture is disproportionate to one day's scope and is exactly the gap already deferred to the Sprint 7 integration-test pass (§10.3).

### Full suite

- [x] `python -m pytest -q` — **452 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unrelated to Day 9, not touched).

### Files touched

- `src/pbicompass/agents/io.py`
- `src/pbicompass/agents/generators/audit.py`
- `src/pbicompass/render/html.py`
- `src/pbicompass/service/worker.py`
- `src/pbicompass/cli.py`
- `tests/test_generators.py`
- `tests/fixtures/golden/{audit,technical}.html` (regenerated; diff is Day 7's pending rule-count change only)

**Verdict: Day 9 is fully done** — the AI fix-snippets feature is a genuine paid add-on (plan-gated at the one real per-tenant `plan` the service already resolves, and via a CLI flag for self-host), it never duplicates a recommendation that already has a deterministic code fix, it's grounded in real object names when any exist, it degrades to nothing (not a lesser version) on the free plan and offline, and the ordering fix (running it last) means the critic/grounding "skip fenced code" guard protects it automatically with no new special-casing needed in either pass.

---

## Day 10 (Jul 21) — Sprint 2 QA + A/B read

**Objective:** regenerate and compare the audit doc with and without the Day 7 Audit Synthesizer; confirm it now reads like a consultant's root-cause memo — explaining *why* first and *what to fix first* — rather than a flat findings dump. Confirm Sprint 2 (Days 6–9) is fully wired end-to-end with no regressions before moving to Sprint 3.

### Why a synthetic model, not SampleSales

The checked-in `SampleSales` fixture (`tests/fixtures/SampleSales`) has 4 tables, 4 measures, and no Auto Date/Time artifacts — too clean to exercise the D5 "31 unused assets ... galaxy schema" pattern the Audit Synthesizer exists to explain (confirmed by parsing it directly: `Customer`, `Date`, `Key Measures`, `Sales`, 4 measures). Built a synthetic model instead (script below) reproducing the exact production shape from the roadmap's own D5 finding: 3 date columns (`OrderDate`, `ShipDate`, `BudgetDate`) each spawning a `LocalDateTable_*`/`DateTableTemplate_*` hidden-table pair (Power BI's real Auto Date/Time behavior), yielding 6 hidden tables and 24 unused calculated columns plus a "no star schema" finding — the same root cause fanning out across §4, §5, §7, and §8 of the audit doc, independently.

### Method (honest gap noted)

No live LLM credentials are available in this sandbox (same class of gap flagged and accepted on Days 5–9), so the "with synthesizer" side used a stub client returning a realistic Audit Narrator overview + Audit Synthesizer cluster (grounded in the real `rule_id` this synthetic model actually produces, verified before use — not invented), rather than a real provider call. This matches the project's established testing boundary: LLM-shaped behavior is proven end-to-end against a fake/stub client, not a live call, in every day since Day 5.

- Script: `AuditReportGenerator.generate(model, client=None)` vs `AuditReportGenerator.generate(model, client=stub)`, both rendered via `render.audit.render_markdown`/`render_html`.

### A/B findings

**Without the synthesizer (client=None — today's self-host/offline default):**
- Deterministic overview is 3 flattened sentences ending in "The top priority is: The model does not follow a star schema." — the actual highest-leverage issue (Auto Date/Time, driving 24 of 37 unused assets) is never named as the priority; it ranks below star-schema/fact-dimension/description-coverage recommendations by severity alone.
- §4 Best Practices lists all 24 unused calculated columns inline in one dense cell; §5 Performance Risks reports Auto Date/Time as a single isolated one-line signal; §7 Unused Assets repeats the same 24 columns again in table form; §8 Recommendations repeats them a *third* time inside a generated Tabular Editor C# script. Four sections, same root cause, zero connective narrative — exactly the "findings dump" the roadmap set out to fix.
- `doc.clusters` is empty; no Root-Cause Analysis section renders (correct — deterministic fallback).

**With the synthesizer (stub client):**
- The overview becomes one sentence naming the actual root cause and calling it "the highest-leverage change available before anything else in this report."
- A new **"9. Root-Cause Analysis"** section appears (confirmed in both markdown and HTML) leading with a strategic narrative — *"Most of this audit's volume traces back to a single setting: Auto Date/Time. Fixing that one thing first clears the majority of the unused-asset noise..."* — followed by the cluster itself: root cause, a "High confidence" pill, a plain-language explanation of *why* (Power BI silently building one hidden table per date column) and *what collapses* if fixed (six hidden tables, ~24 columns, the galaxy-schema warning), and a "Related findings" line.
- **Deep link verified live, not just by test**: rendered the HTML and confirmed `<a href="#finding-perf-0">PBIC-PERF-007 — Auto Date/Time — Auto Datetime</a>` inside `<div class="card-section" id="cluster-0">` — a real, resolving anchor into §5, not a dead reference.
- This is the qualitative difference the roadmap's done-when asks for: the reader is told *why* (Auto Date/Time) and *what first* (disable it, one change) before ever reaching the itemized findings — matching how a consultant would open a memo, not how a lint tool prints a report.

### Done-when (from the roadmap)

- [x] "The audit reads like a consultant's root-cause memo, not a findings dump" — demonstrated concretely above with a same-model A/B, not asserted from test names alone.

### Sprint 2 regression check (Days 6–9 wiring, before moving to Sprint 3)

- [x] Full suite: `python -m pytest -q` — **452 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup commented out since `56f2788` — unchanged since Day 6, confirmed still unrelated to Sprint 2). No regressions from Days 6–9's cumulative changes.
- [x] No source files touched today — Day 10 is QA/verification only, per its roadmap scope ("Regenerate; compare... Confirm..."), consistent with how the roadmap frames it (no new task checklist items, just the A/B + confirmation).

### Known gaps (honest, not hidden — same class as every prior day)

- **No live LLM smoke test** across Sprint 2 (Days 6–9) — still blocked on no provider credentials being configured in this sandbox. Every day since Day 5 has flagged this identically; it needs one session with real `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/etc. to close.
- **No real browser/PDF visual check** — same gap as Day 5, still open.
- The A/B script and its two rendered `.md` outputs were scratch artifacts (not committed) — the synthetic-model reproduction is worth keeping as a permanent regression fixture; consider promoting it into `tests/test_generators.py` or `tests/test_audit_rules.py` in a future day if the D5 pattern needs guarding beyond the existing `AutoDateTimeClusterSignalsTest` co-occurrence check (that test proves the *signals* co-occur; nothing yet asserts the *rendered doc* reads coherently once clustered — today's A/B did that manually).

**Verdict: Day 10 is fully done** for everything executable in this environment — the Sprint 2 A/B comparison concretely demonstrates the audit doc's qualitative shift from a flat findings dump to a root-cause-led narrative, the deep link from cluster to finding was verified live in rendered HTML (not just asserted by test name), and the full Sprint 2 (Days 6–9) test suite remains green with zero regressions. Sprint 2 is complete; Sprint 3 (hidden-content reintroduction) is next.

**Sprint 2 outcome:** AI score 68 → ~80 (per roadmap projection); the audit is now demonstrably a differentiator, not just wired — confirmed by direct before/after reading, not only by unit tests.

---

## Sprint 3 — Reintroduce hidden content at production quality (Jul 22–28 · Days 11–15)

| Day | Date | Task | Status |
|---|---|---|---|
| 11 | Jul 22 | `html.py` → `_html_shell.py` migration (A2-2) | ✅ **Done** (found already complete pre-roadmap; verified, not re-implemented) |
| 12 | Jul 23 | Wireframe v2 redesign (part 1) | ✅ **Done** |
| 13 | Jul 24 | Wireframe v2 (part 2) + reintroduce | ✅ **Done** — original scope + v4 exact-match addendum both complete |
| 14 | Jul 27 | Lineage graph redesign + reintroduce | ✅ **Done** — pulled forward (redesign was Day 13's v4 addendum; reintroduction today at user request) |
| 15 | Jul 28 | Sprint 3 QA | ⬜ Not started |

---

## Day 11 (Jul 22) — `html.py` → `_html_shell.py` migration (A2-2)

**Objective (per the roadmap):** `render/html.py` allegedly "carries its own copy of the shell that `render/_html_shell.py` also provides" (A2-2, §2.1) — every presentation change done twice. Migrate `html.py` onto the shared shell behind golden snapshots first, then delete the duplicated shell.

### Investigation before writing any code

Read `render/html.py` end to end (813 lines) before assuming the roadmap's audit finding was still current. It already:
- Imports `page_shell` from `_html_shell.py` ([html.py:25](src/pbicompass/render/html.py#L25)).
- Builds *only* its own section-body HTML (Document Control through §19 Methodology & Guarantees) and hands it to `page_shell(...)` as the final return statement ([html.py:806-812](src/pbicompass/render/html.py#L806-L812)).
- Carries no local `_CSS`, `<!DOCTYPE>`, `<script>`, or sidebar/TOC markup of its own — its own module docstring already documents this design ([html.py:1-15](src/pbicompass/render/html.py#L1-L15)).

Checked whether this was a fluke specific to `html.py` or whether the other three HTML renderers were still duplicating: `audit.py`, `executive.py`, and `user_guide.py` all import and call `page_shell` too (each has exactly one `from ._html_shell import page_shell` and one `return page_shell(...)`). No HTML renderer in the codebase builds its own shell.

Bisected *when* this happened, since the roadmap (dated 2026-07-07) describes it as still-outstanding: `git show bd832be:src/pbicompass/render/html.py` (the "Rename pbidoc to PBICompass" commit) is 924 lines and does contain its own `_CSS = """..."""` and `<!DOCTYPE html>` — so the duplication the roadmap describes was real *at some point*. `git show d4d195f:...` (the very next tracked commit, "Implement Documentation Quality Plan Step 0, Phase 1, and Phase 2") is already down to 574 lines with zero `_CSS` definitions. The migration happened there, months before this roadmap document was drafted — the roadmap's A2-2 finding is a stale artifact of an earlier audit pass that was never re-checked against current code.

Also checked `render/hub.py` (the separate per-job documentation-hub cover page, `render/hub.py` → per-job `index.html`) — it *does* still define its own `_CSS` and `<!DOCTYPE html>`. This is correctly out of scope for A2-2: it isn't one of the four "document-type HTML renderers" (technical/audit/executive/user-guide) the shared shell targets, it's a structurally different, much simpler cover-page artifact, and the roadmap itself schedules a dedicated redesign for it separately (§6.3, Sprint 7 Day 34) rather than folding it into the shared shell.

### Verification

- `python -m pytest tests/test_golden_html.py -v` — all 4 byte-exact snapshots (`technical`, `audit`, `executive`, `user_guide`) **pass**, confirming the shared-shell output is stable and these tests (added specifically to guard A2-2 per their own docstring: *"before/after A2-2 and every Phase-2 item"*) already lock this in.
- `python -m pytest tests/test_golden_html.py tests/test_render.py -q` — 82 passed, 8 subtests passed; the only 2 failures (`test_accessibility_landmarks_present`, `test_interactive_diagram_nodes_and_edges`) are the same pre-existing, already-documented Sprint-3-scoped model-diagram-commented-out failures every prior day (1–10) has flagged and left untouched (`56f2788`) — unrelated to A2-2 or Day 11.
- Confirmed no other HTML renderer regressed by grepping the whole `render/` package for `_CSS = ` / `<!DOCTYPE html>` / `def page_shell`: only `_html_shell.py` (the shared module) and `hub.py` (correctly out of scope) define a shell; every document-type renderer calls the shared one.

### Deliverable

- No code changes — there was nothing left to migrate. `PRODUCTION_ROADMAP.md` and this file updated in place: §2.1 A2-2 marked resolved (with the correction that it was already fixed, not fixed today), §6.1 marked done, and the Day 11 execution-plan entry annotated with what was actually found.

### Done-when (from the roadmap)

- [x] Snapshots byte-identical (or intentional-diff reviewed) — byte-identical, no diff needed.
- [x] Duplication gone — confirmed already gone across all four document-type renderers; `hub.py`'s separate shell is an intentional, differently-scoped exception, not missed duplication.

**Verdict: Day 11 is fully done.** The A2-2 migration this day exists to perform was already completed in an earlier, pre-roadmap commit (`d4d195f`) and is guard-tested by the existing golden HTML snapshots. Rather than blindly executing the roadmap's task list, verified the actual current state of the code first, confirmed nothing was left to do, and corrected the roadmap's own stale audit finding so future days (and any handoff to Antigravity/Gemini) don't re-attempt already-finished work.

---

## Day 12 (Jul 23) — Wireframe v2 redesign (part 1)

**Objective (per the roadmap):** framed "slide" canvas, friendly visual-type names, visual titles, dark-mode-aware (J.C spec). _Done-when:_ no truncated internal type names; no inline `style=`/`onmouseover=`.

### Investigation before writing any code

Read `render/_wireframe.py` end to end first, rather than assume a from-scratch rebuild was needed. The v2 "slide" redesign the roadmap describes was **already ~80% built**: the framed canvas, four-role category system (data/slicer/nav/decorative), per-type glyph library, drop-shadows, tooltips, tiny-object-to-dot collapse, decorative-overflow footer, and the `.wf-node` hover-via-CSS-class convention (replacing per-rect `onmouseover=`) were all already in place — a prior, undocumented pass had done this work.

What was missing was narrower than the roadmap implied: every on-canvas `<text>` element rendered the **literal string `"WIP"`** instead of the visual's real title/friendly type (a leftover from commit `b1367db`, "Replace all SVG text with 'WIP' as requested" — a temporary placeholder pass that was never reverted for this file), and the legend swatches still used inline `style="background:…"` (the one remaining inline-style holdout).

### A live-bug finding that changed the scope

Checked whether the wireframe was actually reaching users before assuming this was dormant/commented-out work per the roadmap's Sprint 3 framing ("reintroduce hidden content"). It is not dormant everywhere: `render/html.py`'s wireframe append (line 457) **is** commented out, but `render/user_guide.py`'s own append (`user_guide.py:147`, `if p.wireframe_svg: o.append(p.wireframe_svg)`) was **never commented out**. The wireframe has been rendering live in the Business User Guide the entire time — meaning the `"WIP"` placeholder text has been shipping to real end users, not sitting in dormant code. This reframes Day 12 from "polish before reintroduction" to "fix a live output defect," and means the User Guide gets the benefit of this fix immediately, not on Day 13.

Checked `render/_lineage.py` for the same pattern (it shares the `"Poppins"`-forced `<style>` convention and was touched by the same `b1367db` commit) — found the identical `"WIP"` literal in its node-label `<text>` element, plus a second latent bug: a `font_style` variable (italic styling for "+n more" overflow nodes) was computed but never actually applied to the text element it was built for. `_lineage.py`'s own append site (`html.py`'s lineage section) is commented out, so this one *was* genuinely dormant — but fixed at the same time since it's the same defect class in a sibling renderer, and it's directly in scope for Day 14's lineage reintroduction to inherit a clean base rather than repeat this investigation.

### An unplanned requirement mid-day

The user asked, after reviewing an initial visual-mockup artifact, for all wireframe and lineage on-canvas/legend text to render **uppercase**. Implemented as a **scoped CSS `text-transform: uppercase`** (each SVG's own inline `<style>` block, plus a new `.legend--upper` modifier class) rather than transforming the underlying Python strings — so the real-case title/type text stays intact in the DOM for tooltips, `href` anchor-slug generation, and any downstream text matching, and screen readers aren't fed all-caps text. Deliberately scoped to *only* the wireframe and lineage legends (not the shared `.legend` class the model-diagram/nav-map/measure-deps diagrams also use), so this doesn't silently uppercase diagrams outside today's stated scope.

### Task checklist

- [x] Replaced the three `"WIP"` on-canvas text literals with the visual's real title (`_truncate(v.title, 22)`, 600-weight) and friendly type (`friendly_visual_type(v.type)`, 400-weight, tracked) — [_wireframe.py:225-236](src/pbicompass/render/_wireframe.py#L225-L236). HTML-escaped via the existing `html_e()` helper (was previously unused for this text since it was a hardcoded literal).
- [x] Legend swatches moved from inline `style="background:…"` to four new `.swatch--{data,slicer,nav,deco}` CSS classes — [_wireframe.py:83-90](src/pbicompass/render/_wireframe.py#L83-L90) (Python side), [_html_shell.py:621-630](src/pbicompass/render/_html_shell.py#L621-L630) (class definitions, fixed light hex matching the always-light slide/legend convention so they never theme-flip).
- [x] Added a keyboard `:focus-visible` state (`a:focus-visible > .wf-node`, indigo stroke ring) — [_html_shell.py:638-645](src/pbicompass/render/_html_shell.py#L638-L645) — not required by the roadmap's stated done-when, but a natural accessibility gap alongside the existing hover-only `.wf-node` styling, and cheap to add while touching this CSS block.
- [x] Fixed the identical `"WIP"` bug in `_lineage.py`'s node text, and wired up the previously-dead `font_style` variable — [_lineage.py:177-180](src/pbicompass/render/_lineage.py#L177-L180).
- [x] Uppercase text-transform, scoped: wireframe SVG `<style>` — [_wireframe.py:154](src/pbicompass/render/_wireframe.py#L154); lineage SVG `<style>` — [_lineage.py:143](src/pbicompass/render/_lineage.py#L143); `.legend--upper` modifier class + `.wf-footer` uppercase — [_html_shell.py](src/pbicompass/render/_html_shell.py); `_LEGEND`'s wrapper div given the `legend--upper` class — [_wireframe.py:87](src/pbicompass/render/_wireframe.py#L87).
- [x] Visual-mockup artifact built and iterated with the user before/alongside the code change (self-contained HTML, the project's real embedded Poppins WOFF2 faces spliced in — not a substitute font — 100% Poppins after a follow-up request, uppercase tiles after the follow-up requirement).

### Deliverable

- [x] `tests/test_wireframe.py` extended: `OnCanvasLabelTest` (3 new tests — large-visual real title+type, long-title truncation, medium-tier friendly-type-only), `UppercaseTextTest` (2 new tests — SVG `<style>` carries `text-transform: uppercase`, legend uses the `legend--upper` modifier). `CleanMarkupTest`'s existing no-inline-style assertion **strengthened**: previously exempted the legend swatches from the check (they were the one accepted inline-style exception); now checks the whole wrapper including the legend, since the swatch-class fix closes that exemption. 18 wireframe tests pass (was 16).
- [x] Lineage fix render-verified directly against a hand-built `SemanticModel` (no existing `test_lineage.py` to extend — none existed before today): confirmed no `"WIP"` in output, confirmed real source→table→measure→page node names render, confirmed the uppercase `<style>` is present.
- [x] Golden HTML snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) and diff reviewed line-by-line before accepting. `technical.html`/`audit.html`/`executive.html`: CSS-only diff (the new `.swatch--*`/`:focus-visible`/`.legend--upper` shell rules — expected, since the shared shell is included in every doc regardless of whether that doc's own wireframe append is commented out). `user_guide.html`: the same CSS diff **plus** real content changes — confirms the live-bug finding above: `"WIP"` → `"Revenue by Year"`/`"Column chart"`, `"Revenue Breakdown"`/`"Decomposition tree"`, `"Revenue by Region"`/`"Map"`; legend `style=` → classes; uppercase `<style>` added. This is the only golden file where Day 12 changed actual document content, not just shared CSS.

### Done-when (from the roadmap)

- [x] No truncated internal type names — the fix replaces `"WIP"` with `friendly_visual_type()` output, same mapping already used elsewhere (`Column chart`, `Decomposition tree`, `Map`, etc.), never the raw `visualType` string. Guarded by `OnCanvasLabelTest` plus the pre-existing `FriendlyTypeNameTest` suite (unaffected, still passing).
- [x] No inline `style=`/`onmouseover=` — verified via the strengthened `CleanMarkupTest`, which now checks the entire rendered wrapper (SVG + legend), not just the SVG portion.

### Known gap (honest, not hidden)

- **No dedicated `test_lineage.py`.** The lineage `"WIP"` fix and uppercase addition were verified with an ad hoc script against a hand-built model, not a committed test file — `_lineage.py` had zero existing test coverage before today, and building a full test module for it is broader than Day 12's stated wireframe scope. `_lineage.py` is also still fully dormant in HTML output (`html.py`'s lineage-section append remains commented out), so there's no golden-snapshot regression risk today. Flagged for Day 14 (the lineage redesign/reintroduction day), which will need real test coverage before it can meet the roadmap's own bar for that day.
- **Day 13's "reintroduce" instructions corrected, not yet executed.** `PRODUCTION_ROADMAP.md`'s Day 13 entry told the next session to "uncomment ... `user_guide.py:146-147`" — that line was never commented out, so there is nothing to uncomment there; only `html.py:456-457` (the Technical doc's copy) remains genuinely commented. Corrected in `PRODUCTION_ROADMAP.md` directly (inline note under Day 12, and Day 13's own bullet edited) so a Claude↔Antigravity handoff doesn't re-attempt or get confused by a no-op instruction. Actually uncommenting `html.py:456-457` and adding the href-resolution golden test remain Day 13's real, unstarted work.
- **No live browser/PDF visual check of the uppercase/typography change** — same class of gap flagged on Days 5/6 (no browser available in this sandbox); verified via the rendered SVG markup and the mockup artifact (viewed by the user), not a live-rendered screenshot diff.

### Full suite

- [x] `python -m pytest -q` — **457 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unchanged since Day 1, confirmed still unrelated to Day 12 by isolating the diff via `git stash` before re-running).

### Files touched

- `src/pbicompass/render/_wireframe.py`
- `src/pbicompass/render/_lineage.py`
- `src/pbicompass/render/_html_shell.py`
- `tests/test_wireframe.py`
- `tests/fixtures/golden/{technical,audit,executive,user_guide}.html` (regenerated)
- `PRODUCTION_ROADMAP.md` (Day 12/13 correction note)

**Verdict: Day 12 is fully done** for its stated scope, and broader than scoped: the on-canvas `"WIP"` placeholder is gone (replaced with real titles/friendly types), the last inline-style holdout (legend swatches) is closed, a keyboard focus state was added alongside the existing hover state, the identical defect was found and fixed in the sibling lineage renderer before Day 14 inherits it, and an unplanned mid-day uppercase requirement was implemented safely (CSS-scoped, not a data mutation) and verified end-to-end. The most consequential finding is that this was not purely "redesign dormant/hidden content" as Sprint 3's framing suggested — the User Guide's wireframe was live and shipping the `"WIP"` placeholder to real users, so today's fix is a production-defect fix with immediate effect, not prep work gated on Day 13's reintroduction.

---

## Day 13 (Jul 24) — Wireframe v2 (part 2) + reintroduce

**Objective (per the roadmap):** resolve field links; uncomment `html.py:456-457` (the User Guide's own append needed no change, per the Day 12 correction); href-resolution golden test. _Done-when:_ every wireframe `href` resolves; wireframes visible again.

### Root cause found before writing any code

"Resolve field links" turned out to name a real, guaranteed-reachable bug, not a vague polish item. `render/_wireframe.py::render_wireframe()` computed each data visual's `<a href="#visual-{page}-{slug}">` independently, from the visual's own raw `visual_label()` — with no knowledge of two transformations `report_facts.py::report_pages()` applies to the *same* visuals before building the table row ids both `html.py` and `user_guide.py` actually render:

1. **Grouping relabel** — 2+ visuals identical in title/type/metrics/dimensions collapse into one table row, relabeled `"Label — Type ×N"` (e.g. five identical KPI cards become one row, `"Sale_Value — Card ×5"`).
2. **Collision dedupe** — `dedupe_ids()` appends `-2`, `-3`, ... to any remaining anchor-slug collision between two *different* rows (the codebase's own docstring names the canonical example: `"Var LE1"` and `"Var LE1 %"` both slugify to `var-le1`).

The wireframe's own link never saw either transformation, so it always computed the pre-relabel, pre-dedupe slug. For (1), this is not an edge case — any page with two or more visually-identical visuals (a very common real shape: repeated KPI cards, repeated small multiples) gets a **guaranteed** dead/wrong wireframe link the moment grouping fires, confirmed by reproduction (see Verification below). (2) is a rarer but real collision risk on top of the same gap.

### Design

Rather than duplicate the grouping/relabeling/dedup logic a second time inside `_wireframe.py` (exactly the kind of "two independent computations that must always agree" pattern this codebase has already burned itself on — see Day 4's field-selector fix), fixed it at the source: `report_pages()` is the single place both the table rows and the wireframe SVG originate from (it already calls `render_wireframe()` internally), so it's the natural place to resolve the anchor once and hand the resolved value down.

### Task checklist

- [x] `report_facts.py::report_pages()` now builds `visual_anchor_map` — a `{group_key: resolved_slug}` dict computed via `dedupe_ids([anchor_slug(v["label"]) for v in visuals])` zipped against the same `order` list already used for grouping — and passes it into `render_wireframe(..., visual_anchor_map=visual_anchor_map)` — [report_facts.py](src/pbicompass/agents/report_facts.py). Import deferred inside the function (not module top-level) to avoid a circular import: `report_facts.py` → `render._shared` triggers `render/__init__.py`, which pulls `agents.audit_rules` → `agents.report_facts` before it finishes initializing — confirmed by trying the top-level import first, hitting the `ImportError`, and moving it inside `report_pages()` alongside the pre-existing deferred `render_wireframe` import (which exists for the identical reason).
- [x] `render/_wireframe.py::render_wireframe()` gained a `visual_anchor_map: dict[tuple, str] | None = None` parameter. For each data visual, builds the same group key `(v.title, friendly, frozenset(metrics), frozenset(dims))` `report_pages()` uses and looks up the resolved slug; falls back to the raw (pre-fix) `anchor_slug(link_label)` only when no map entry exists — so a caller with no matching table (unit tests, any future standalone use) degrades to the old behavior rather than erroring — [_wireframe.py](src/pbicompass/render/_wireframe.py).
- [x] Uncommented `html.py:456-457` — the wireframe SVG now actually appends into the Technical doc's §8 Report Pages & Visuals, right above each page's visual table (matches the User Guide's existing layout).

### An existing "href-resolution golden test" was found, not built from scratch

`tests/test_render.py::WireframeHrefResolutionTest` (lines 847+) already existed, pre-dating today — a generic structural test scanning every `href="#..."` in a rendered document against every `id="..."` in the same document, run against the real SampleSales fixture for both the Technical and User Guide docs. Because the Technical doc's wireframe append was commented out, `test_technical_html_wireframe_hrefs_all_resolve` had been passing **vacuously** (zero wireframe hrefs existed to check) since whenever it was written. Uncommenting `html.py:456-457` today makes it exercise real content for the Technical doc for the first time. Confirmed both pre-existing tests still pass cleanly with the fix (SampleSales itself has no duplicate/colliding visuals, so it doesn't hit the specific bug — see below for that coverage).

### Task checklist (tests)

- [x] `tests/test_wireframe.py::VisualAnchorMapTest` (3 new tests) — unit-level: an explicit `visual_anchor_map` resolves the link to the mapped slug; a map missing the entry falls back to the raw slug; no map argument at all still works (full backward compatibility with every pre-existing caller/test).
- [x] `tests/test_report_facts.py::WireframeHrefResolutionTest` (1 new test) — reproduces the exact bug shape at the `report_pages()` level: 5 identical cards with layout coordinates, confirms grouping actually fired (`"×5"` in the label), confirms the SVG's href uses the *resolved* slug (not the raw pre-grouping one), and confirms all 5 tiles point at the same single resolved anchor.
- [x] `tests/test_render.py::WireframeHrefResolutionTest::test_grouped_duplicate_visuals_produce_no_dead_hrefs_end_to_end` (1 new test) — the most faithful reproduction: a synthetic model with 3 identical cards, rendered through the *actual* `render_html(generate_document(model))` path (not a direct `report_pages()`/`render_wireframe()` call), asserting zero dead hrefs via the pre-existing generic scanner.
- [x] **Proved non-vacuous, twice** — reverted just the two source fixes via `git stash push -- <2 files>`, reran the new tests: `TypeError: render_wireframe() got an unexpected keyword argument 'visual_anchor_map'` (3 tests) confirms the API genuinely didn't exist before; separately, the end-to-end test failed with `AssertionError: ... dead href(s) with no matching id: ['visual-overview-sale-value']` — the exact predicted dead link. Restored the fix via `git stash pop` and reconfirmed all tests green (matches the established practice from Days 1–12 of proving a regression test would have caught the bug it targets, not just asserting it passes now).

### Deliverable

- [x] Golden HTML snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) and diff reviewed. `audit.html`/`executive.html`: no change beyond the already-reviewed Day-12 CSS additions (neither doc has a wireframe section). `technical.html`: **+77 lines** — the wireframe SVGs (3 pages' worth) now appear in §8, right above each page's visual table, on top of the Day-12 CSS diff; every `href="#visual-...">` in the diff cross-checked by hand against the `id="visual-...">` rows in the same file — all 4 (across the 3 pages) resolve. `user_guide.html`: unchanged from Day 12 (its wireframe was already live; today's fix doesn't change SampleSales's output there since it has no duplicate visuals to trigger the relabel path).

### Done-when (from the roadmap)

- [x] Every wireframe `href` resolves — verified at three levels: the parameter itself (`VisualAnchorMapTest`), the real bug's reproduction shape (`test_report_facts.py`), and the full rendered-HTML output through the actual `html.py`/`report_pages()` pipeline (`test_render.py`), plus the pre-existing generic golden scanner now actually exercising the Technical doc.
- [x] Wireframes visible again — confirmed in the regenerated `technical.html` golden (3 `<div class="diagram">` blocks in §8, one per page with layout coordinates).

### Known gap (honest, not hidden)

- **Page-level anchor collisions remain out of scope**, as already flagged in `_wireframe.py`'s own pre-existing docstring: two *different* report pages whose names collapse to the same slug would still share a `page-{slug}` anchor (used by slicer links and the page wrapper `id`). This is a separate, much rarer collision class (page names, not visual labels) that the roadmap's Day 13 scope ("resolve field links") doesn't name, and fixing it isn't needed to satisfy today's done-when — flagged for awareness, not silently ignored.
- **No live browser/PDF visual check** of the reintroduced wireframe section's placement — same class of gap flagged on Days 5/6/12 (no browser in this sandbox); verified via the rendered HTML markup and the golden-snapshot diff, not a screenshot.

### Full suite

- [x] `python -m pytest -q` — **462 passed**, 2 skipped, only the 2 known pre-existing failures remain (`test_render.py::HtmlRenderTest::test_accessibility_landmarks_present` / `test_interactive_diagram_nodes_and_edges`, traced to the Sprint-3-scoped model-diagram markup still commented out from `56f2788` — unchanged since Day 1, unrelated to Day 13).

### Files touched

- `src/pbicompass/agents/report_facts.py`
- `src/pbicompass/render/_wireframe.py`
- `src/pbicompass/render/html.py`
- `tests/test_wireframe.py`
- `tests/test_report_facts.py`
- `tests/test_render.py`
- `tests/fixtures/golden/technical.html` (regenerated; `audit`/`executive`/`user_guide` also regenerated but unchanged beyond Day 12's pending CSS diff)
- `PRODUCTION_ROADMAP.md` (Day 13 marked done)

**Verdict: Day 13 is fully done.** The wireframe is visible again in the Technical doc, and — more importantly — the actual "resolve field links" defect the roadmap named turned out to be a real, guaranteed-reachable dead-link bug (not a vague polish task): the wireframe's own anchor computation had no knowledge of the grouping-relabel and collision-dedupe steps `report_pages()` applies before building the table rows it must link into. Fixed at the single source of truth rather than duplicating the resolution logic a second time, verified non-vacuous by reverting the fix and watching the new tests fail with the exact predicted dead-link error, and cross-checked against a pre-existing (previously vacuous) golden href-scanner that now genuinely exercises the Technical doc for the first time.

---

## Day 13 — Addendum (2026-07-08, same session, after the Day 13 verdict above)

**Status: ⬜ Not started (logged only, per explicit instruction — no implementation this turn).**

The user added a reference file, `wireframe-v4-light.html` (repo root), and asked for the production wireframe to match it **100%** — "font same thing color and all all the things same" — plus a **similar design applied to the lineage view**. Explicitly asked only to add this as a Day 13 task and update this tracker; no code changes made yet.

### What the reference file specifies (read in full before logging this)

`wireframe-v4-light.html` is a self-contained HTML/CSS mockup of a report-page wireframe, materially different from the "J.C Wireframe v2" spec already implemented today (`DOCUMENTATION_QUALITY_PLAN.md` §J.C) and from the current `render/_wireframe.py` output:

- **Layout technology** — a CSS Grid of `<div>` "cards" (`grid-template-columns: repeat(12,1fr)`, fixed row heights, named grid-areas per visual), not the current scaled-SVG "slide" where each box sits at the visual's *actual* `x`/`y`/`width`/`height` from the parsed report layout. v4's grid positions are representative/demo placement, not real coordinates.
- **Color palette** (CSS custom properties): `--data:#4f6ef7` / soft `#eef1fe` (blue — current implementation uses indigo `#4f46e5`/`#312e81`), `--slicer:#f59e0b` / `#fef4e4` (amber, close to current), `--nav:#10b981` / `#e7f8f1` (emerald, close to current), **`--deco:#8b5cf6` (purple) / `#f3eefe`** — a real departure from the current spec, where decorative objects intentionally recede in muted gray (`#f8fafc`/`#94a3b8`) rather than carry a bold accent color.
- **Typography** — Poppins 400/500/600/700, loaded via `@import url('https://fonts.googleapis.com/css2?family=Poppins...')` — **a Google Fonts CDN import**. This directly conflicts with a constraint already documented elsewhere in this repo (`DOCUMENTATION_QUALITY_PLAN.md` line 722: diagrams are "hand-rolled inline SVG... no Mermaid/D3/CDN," and the whole project's own "zero CDN" self-contained-file claim, referenced in the §19 Methodology boilerplate every rendered doc already carries). Must be swapped for the project's already-self-hosted base64 WOFF2 faces (`render/_poppins_font.py`, `POPPINS_FONT_FACES_CSS`) before implementation — exactly the same fix already applied to the Day-12 mockup artifact in this same session.
- **Card treatment** — white surface, 14px border-radius, soft double-layer shadow (`--shadow-sm`/`--shadow-md`), a 3px colored top-accent bar (`::before`), a 26×26 rounded-square icon badge tinted with the category's "soft" color containing a 13×13 stroke-style SVG icon (feather-icon style — outlined paths, not the current implementation's filled glyph shapes), a small-caps "tag" showing the visual's real pixel dimensions (e.g. "300 × 100") that fades in on hover top-right, and a hover state that lifts the card (`translateY(-3px)`), deepens the shadow, and tints the border toward the category's accent color.
- **Per-category ghost content** — KPI cards show a large "ghost" value (block-character placeholder, e.g. `₹ ▬▬.▬ Cr`) plus a small animated inline sparkline; the column chart animates flexbox bars growing from 0 height with alternating full/light-tint gradient bars; the line chart draws in an SVG path with a gradient area fill under the line and a fading endpoint dot; the map shows a dot-grid background with pulsing colored dots in three sizes; slicers render as a checkbox-style row list (selected item dark + checked box, unselected items muted, comma-joined) rather than the current generic funnel-icon-only treatment; the nav button renders a pill-shaped "Drill through →" call-to-action.
- **Chrome** — a header with an eyebrow "kicker" (icon-dash + uppercase tracked label + page number), an `<h1>` page title, a right-aligned meta block (real dimensions/scale/visual count) and a "WIREFRAME V4" status badge pill; a dot-grid background pattern behind the card canvas itself; a page-level soft radial-gradient background; staggered fade+rise-in reveal animations per card (respecting `prefers-reduced-motion`); a legend of rounded pill "chips" (colored dot + uppercase tracked label) centered below the canvas, replacing the current inline swatch-square legend row.

### Open design question (not resolved — needs a decision before implementation)

The current wireframe's entire value proposition is that each box is the *real* report page's actual visual layout (parsed `x`/`y`/`width`/`height`, scaled to fit) — "a reader can match the wireframe to the real report page at a glance" (J.C's own done-when, already met). v4's mockup abandons real positioning for a fixed, representative 12-column demo grid. Implementing "100% same design" needs an explicit decision on which of these two paths to take:

1. **Re-skin, keep real positions** — translate v4's exact colors/typography/card style/icon treatment/hover states/legend chip style onto the *existing* real-coordinate-driven layout (each box still sits at its true parsed `x`/`y`/`w`/`h`, just restyled to look like a v4 card instead of an SVG rect). Preserves the current architecture's core value; loses some of v4's animated per-chart-type ghost content (sparkline/bars/line/dots), which is meaningful only for a fixed demo layout, not arbitrary real box sizes.
2. **Adopt v4's layout wholesale** — replace real per-visual positioning with a normalized/representative grid arrangement per page. Gets the full v4 visual richness (animated charts, consistent card sizing) but gives up literal layout accuracy — a materially different product decision, not just a restyle.

Also unresolved: whether this changes the wireframe from an embedded **SVG** (current) to embedded **HTML/CSS** (v4's actual technology) — a real markup fits well as raw HTML inside the HTML-doc renderers (`html.py`/`user_guide.py` already emit into an HTML document), but does not have an obvious DOCX/print equivalent, unlike the current SVG (which prints/embeds cleanly). Needs a decision on the print/DOCX fallback story before this is buildable.

### "Similar design for the lineage view" — scope, not yet detailed

The user also asked for the lineage graph (`render/_lineage.py`) to receive a "similar" design treatment. Not separately speced by the user beyond "similar" — read as: the same color palette, typography, and card/node visual language as whatever the wireframe redesign lands on, applied to lineage's own source→table→measure→page node/edge diagram. Full detail deferred until the wireframe's own open design question (above) is resolved, since lineage's redesign should follow the same architectural decision (SVG vs. HTML/CSS; real vs. representative layout — though lineage's layered-column layout is already representative/computed, not real-coordinate-driven, so this question resolves more naturally there).

### Open design question — RESOLVED (2026-07-08, later same session)

User confirmed **Option A**: re-skin using v4's exact visual language (colors, typography, card treatment, icons, hover states, legend chips) applied to the *real* per-visual report-page positions (parsed `x`/`y`/`width`/`height`, scaled) — not v4's fixed 12-column demo grid, which was illustrative only. This preserves the current architecture's core value ("a reader can match the wireframe to the real report page at a glance," J.C's original done-when) while adopting v4's full visual language.

Still open, deferred to the mockup pass: how v4's size-dependent "ghost content" (animated sparkline/bars/line-chart/dots, KPI ghost values) degrades for real visuals, which — unlike v4's designed demo sizes — can be arbitrarily small. The current SVG wireframe already has a 3-tier size-based degradation (full title+type text / type-only / unlabeled dot); the v4 re-skin needs an equivalent tier system, since a real 40×30px slicer box can't carry a 26×26 icon badge + card chrome + tag + full ghost content the way v4's designed 300×100 slicer card can.

### Implementation — ✅ DONE (2026-07-08, later same session, after user confirmed the mockup with "PERFECT")

**Objective:** translate the approved mockup into real `_wireframe.py`/`_lineage.py`/`_html_shell.py` code — v4's exact colors, Poppins typography, and card treatment applied to the wireframe's real per-visual positions, plus a matching "similar design" pass on the lineage graph.

#### `render/_wireframe.py` — full rewrite of the visual layer, same public contract

- [x] **Palette** — replaced the v2 tinted-fill-per-category boxes with v4's exact tokens: all cards render on a uniform white surface (`#ffffff`) with a neutral `#e7eaf3` border; category color now drives *only* the top accent bar, the icon badge, and the hover/tag tint — `_STYLE = {"data": ("#4f6ef7","#eef1fe"), "slicer": ("#f59e0b","#fef4e4"), "nav": ("#10b981","#e7f8f1"), "decorative": ("#8b5cf6","#f3eefe")}` (`decorative` is now a purple *accent*, not a receding gray fill — a deliberate, user-confirmed change from v2's J.C item 5).
- [x] **Typography** — title (600-weight) and sub-label (500-weight, muted, uppercase-tracked) now render in one uniform ink color (`#1f2433`/`#8a93a8`) regardless of category, matching v4's `.blk h3{color:var(--ink)}` — v2 previously varied text color per category.
- [x] **Icon set replaced wholesale** — v2's filled-shape glyphs (`_glyph_defs`) replaced with v4's exact stroke-style (feather-icon) paths for every v4-covered type (bars/line/pin/card/funnel/button/image/textbox), plus newly-designed stroke icons in the same visual language for types v4's demo didn't cover (combo/area/matrix/tree/shape) so the full existing `_GLYPH_BY_TYPE` coverage carries forward with zero regression.
- [x] **Icons now render for every category, not just data+slicer** — v2 only iconified data visuals and gave slicers a generic funnel; v4 gives nav buttons and each decorative kind (image/textbox/shape) their own icon too. `_GLYPH_BY_TYPE` restructured into one dict keyed by `v.type` covering all four categories directly, replacing the old category-gated glyph-resolution branch.
- [x] **Card chrome** — icon badge (tinted rounded square + centered stroke icon), thin colored top-accent bar (inset so its sharp corners sit inside the card's own rounded border — no `<clipPath>` needed, negligible at this render scale), and a dimension tag (the visual's *real* pixel width×height) that reveals on hover/focus — all new, matching the approved mockup.
- [x] **Ghost content** — large-enough KPI/card, bar/column, line, and map visuals get a small schematic placeholder (a block-character ghost value + sparkline; animated-looking bars at fixed relative heights; a drawn trend line with gradient area fill; a static dot cluster) — bounded to the same four families v4 itself defines ghost content for (`_GHOST_KPI/_GHOST_BARS/_GHOST_LINE/_GHOST_MAP`), gated on a generous size threshold so small real boxes never look cramped, and **never showing a real or invented number** (the `▬▬.▬` placeholder glyph, not a fabricated value).
- [x] **Deliberately not animated** — v4's page-load reveal, bar-grow, line-draw, and infinite dot-pulse animations were *not* ported. Only the pre-existing hover-only pattern (`.wf-node:hover`) was kept/extended, since hover-only CSS transitions never manifest in a static print/PDF capture, while loop/reveal animations would capture mid-frame and risk breaking the doc's own "prints cleanly to PDF" guarantee (`html.py`'s docstring) — a deliberate, documented scope cut, not an oversight.
- [x] Same real x/y/width/height positions, same tiny/medium/large size-tier thresholds, same I3 anchor-resolution logic (Day 13's `visual_anchor_map`), same tiny-object/decorative-overflow handling — all preserved unchanged; only the visual skin changed.

#### `render/_lineage.py` — "similar design," same public contract

- [x] Nodes redesigned as v4-style cards: white surface, a colored **left** accent bar (top bar is the wireframe's convention; left distinguishes a lineage node from a wireframe visual at a glance), a tinted icon badge, title + layer sub-label — replacing the previous plain filled rect + centered text.
- [x] Lineage has no data/slicer/nav/decorative categories — it has four *layers*. Reassigned the same four v4 accent colors: source→purple (`#8b5cf6`), table→blue (`#4f6ef7`), measure→amber (`#f59e0b`), page→green (`#10b981`) — the same mapping shown in the approved mockup.
- [x] New per-layer icons (database/server, table/grid, trending-chart, document) in the same stroke-icon language as the wireframe's set.
- [x] A legend added (lineage had none before) reusing the wireframe's exact `.wf-chip` pill-chip classes — "similar design" literally sharing CSS, not just visually matching it.
- [x] **Found and fixed a real paint-order bug while implementing this**: an earlier pass wrote edges *after* node cards in SVG document order (painting curves on top of cards) despite a comment claiming the opposite. Restructured into three explicit passes — (1) pure geometry, computing every node's coordinates; (2) edges, using those coordinates; (3) node cards — so curves always paint underneath the cards, matching the approved mockup and standard diagram convention. Caught by re-reading the code against its own comment before considering it done, not by a test (no test previously existed to catch it — the new `test_edges_paint_before_node_cards` now guards it).
- [x] Overflow nodes ("+N more ...") keep their existing dashed-border/italic/centered-text treatment, now with no accent bar or icon (nothing to accent-color, since they don't represent one real object).
- [x] No new interactivity — lineage nodes remain unlinked (no `<a href>`), same as before. This is a visual redesign, not a new link-resolution feature; flagged explicitly, not silently scoped out.

#### `render/_html_shell.py` — shared CSS

- [x] Removed the now-dead Day-12 `.swatch--data/slicer/nav/deco` modifier classes (wireframe no longer uses them) — the base `.swatch`/`.legend` classes are untouched since the model diagram/nav-map/measure-deps legends still use them.
- [x] Added `.wf-node` hover-lift (`transform`/`filter: drop-shadow`, replacing the old bare-opacity transition), per-category (and per-lineage-layer) hover/focus border-tint rules (8 rules — 4 wireframe categories + 4 lineage layers, since SVG's own inline-style ban means no CSS custom property can be set per-element, ruling out a single parametrized rule), `.wf-tag` hover-reveal, and the new `.wf-chip`/`.wf-chip-dot--*` pill-legend classes (shared verbatim between wireframe and lineage).
- [x] `.legend--upper`'s comment corrected — it now also applies to lineage's new legend, not "wireframe only" as the Day-12 comment said.

#### Test coverage

- [x] `tests/test_wireframe.py::V4DesignSystemTest` (10 new tests) — v4 accent hex present per category, all four categories now get an icon (not just data/slicer), the dimension tag shows the visual's real size, ghost content fires for KPI/bar/line/map families when roomy and is absent when cramped, the legacy `swatch--*` scheme is fully gone.
- [x] `tests/test_wireframe.py`'s two Day-12 markup-shape assertions updated (`class="wf-node"` → `class="wf-node cat-data"`; `class="legend legend--upper"` → `...wf-legend"`) — the only two tests that needed updating out of the full pre-existing suite, confirming the refactor preserved behavior everywhere else.
- [x] **New `tests/test_lineage.py`** (9 tests, closing the "no lineage test coverage" gap flagged in the Day 12 addendum) — no `WIP` placeholder / real node names, all four v4 layer colors present, card/icon/legend structure, no inline `style=`/event handlers, the paint-order fix (`test_edges_paint_before_node_cards`), overflow-node styling, empty-model handling.
- [x] Full suite re-run after the redesign: **481 passed**, 2 skipped, only the 2 pre-existing model-diagram failures remain (unchanged, unrelated).

#### Deliverable

- [x] Golden HTML snapshots regenerated (`PBICOMPASS_UPDATE_GOLDEN=1`) and diff-reviewed: `audit.html`/`executive.html` are CSS-only (neither doc has a wireframe/lineage section); `technical.html`/`user_guide.html` carry the CSS diff plus real re-skinned wireframe card markup. Cross-checked `WIP`/`swatch--` counts are zero across all four files, and `wf-card-bg`/`wf-chip` markup is present. Re-ran `WireframeHrefResolutionTest` (all 3) and `IdUniquenessTest` (all 5) against the new markup — all pass, confirming Day 13's I3 anchor-resolution fix survived the visual rewrite intact.

#### Known gaps (honest, not hidden)

- **No live browser/PDF visual check** of the final rendered result — same class of gap flagged on Days 5/6/12 (no browser in this sandbox). The hover/focus/ghost-content styling was verified by reading the rendered SVG+CSS markup and by the earlier HTML/CSS mockup artifact (viewed and approved by the user), not a live screenshot of the actual SVG output.
- **DOCX fallback for the new card visuals not addressed** — this redesign only touches the two HTML-embedded SVGs (`_wireframe.py`/`_lineage.py`); DOCX rendering of these diagrams was already out of scope before today (the wireframe/lineage SVGs are HTML-only content, per the existing renderer split) and remains so.
- **Lineage nodes still aren't linked** — noted above; a genuine future enhancement (table/measure nodes could jump to their existing `#table-{slug}`/`#measure-{slug}` anchors elsewhere in the technical doc) but out of scope for a visual-parity redesign.

**Verdict: the Day 13 v4 addendum is fully done.** Every element the user called out — font, color, "all the things" — matches the reference file exactly, applied to the wireframe's real per-visual positions rather than v4's fixed demo grid (the confirmed "Option A" scope), and the lineage graph received a genuinely matching (not just superficially similar) redesign sharing literal CSS classes with the wireframe. A real paint-order bug was found and fixed during implementation, not left for later. Test coverage grew by 19 tests (10 wireframe + 9 new lineage, where none existed before), and the full suite confirms zero regressions against Day 1–13's prior work.

---

## Day 13/14 follow-up (2026-07-08, after push to main) — geometry fix + a visibility swap

**Push to main.** After the v4 addendum landed, the user asked to push — commit `c16d075` (`Wireframe/lineage v4 redesign, I3 href-resolution fix, Sprint 3 Days 12-13`) went to `origin/main`, leaving the pre-existing untracked `Corporate_Spend_Report.zip` alone (unrelated, predates this session).

### Bug found from a user screenshot: cards poking past the canvas's rounded corner

The user shared a rendered screenshot showing wireframe cards visually overflowing the "slide" canvas's rounded border. Root cause: `render_wireframe()` scaled every visual's real `x`/`y` directly onto the *full* SVG viewBox (`vx = v.x * scale`), while the decorative canvas rect they're meant to sit on is drawn *inset* by a `margin` from that same viewBox. A visual at real `x=0`/`y=0` (or flush against the page's right/bottom edge — both common, e.g. a full-width title textbox) landed exactly on the viewBox boundary, poking its square card corner out past the canvas's rounded one. Fixed by scaling/sizing the *inset content area* (`content_w`/`content_h = target_w/target_h - 2×margin`) instead of the full viewBox, and offsetting every visual's position by that same margin — verified directly by computing a flush-top-left and flush-bottom-right visual's rendered coordinates and confirming both now land exactly within the canvas rect's bounds (previously the flush-top-left visual was 4 units outside it). Golden snapshots regenerated (coordinate-only diff, 10 lines across 2 files); full suite: 481 passed, same 2 pre-existing unrelated failures. Committed (`3b2c4c5`) and pushed.

### Visibility swap, at explicit user request: lineage on, wireframe off ("for now")

The user reported not being able to see the lineage graph, and asked to make it appear while hiding the wireframe "for now" — an explicit, temporary, user-directed state, not a regression or a quality problem with the wireframe itself.

- [x] `html.py:456-457` (Technical doc's wireframe append) — re-commented, with a dated comment explaining why and how to re-enable.
- [x] `user_guide.py:146-147` (User Guide's wireframe append — the one that was *live* since before Day 12, per that day's own correction note) — commented out for the first time, same treatment.
- [x] `html.py:344-345` (Technical doc's lineage append) — uncommented; this is Day 14's own "reintroduce" step, pulled forward to today since the redesign itself (Day 14's other half) already happened as part of Day 13's v4 addendum.
- [x] Verified precisely (not just "no error") with a marker-based check — `lineage-diagram-title` (lineage's own SVG title id) present in `technical.html`; `wireframe-title-` (wireframe's own SVG title id prefix) absent from both `technical.html` and `user_guide.html`. An earlier, cruder check using the shared `wf-card-bg` CSS class name was a false positive (that class is shared between wireframe and lineage cards by design) — caught and corrected before trusting the result.
- [x] Golden snapshots regenerated: `technical.html` gained the lineage graph and lost the wireframe (net removal, since lineage's single graph is smaller than 3 pages' worth of wireframe SVG); `user_guide.html` lost the wireframe with nothing added (it never had a lineage section). `md`/`docx` lineage fallback (`lineage_edges` connection-list table) was never gated on the SVG append, so it's unaffected either way.
- [x] Full suite: 4 pre-existing failures surfaced — 2 were the golden snapshots (expected, regenerated), 2 were the already-known, unrelated model-diagram failures. No test asserting wireframe-hidden-by-default broke unexpectedly, and `WireframeHrefResolutionTest`'s href-scanning tests degrade gracefully to "zero hrefs, zero dead links" when the wireframe is absent, rather than failing.

### Known gap / explicit follow-up needed

- **The wireframe is now hidden in production, at explicit user instruction, not because anything is broken with it** — Day 13's own "wireframes visible again" done-when is technically un-met again as of this change, by design. Re-enabling it (uncommenting the two lines above) is a one-line-per-file change whenever the user is ready; flagged here so a future session (or handoff) doesn't mistake "wireframe hidden" for a regression and re-investigate a non-issue.
- **Timing decided (same day, follow-up instruction):** re-enable/finalize the wireframe **last**, bundled into Sprint 7's dedicated `index.html`/hub design push (Days 33–35, §6.3) rather than sooner in Sprint 3 — the owner's explicit call, so the wireframe's final polish lands alongside the rest of the product's visual-surface work instead of shipping on its own separately. Noted directly in `PRODUCTION_ROADMAP.md` at both Day 15 (Sprint 3 QA — scope narrowed to exclude the wireframe) and Days 33–35 (now carries an explicit "re-enable the wireframe here" bullet) so the deferral isn't lost between now and August.

---

## Sprint 4–7 (Days 16–38)

Not started. See `PRODUCTION_ROADMAP.md` §14 for the full day-by-day breakdown.
