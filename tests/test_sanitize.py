"""Tests for ``agents/sanitize.py`` (AI-Native roadmap D2/D3/D6): the
deterministic meta-commentary, orphan-fragment, and punt-phrase guards."""

from __future__ import annotations

import unittest

from pbicompass.agents.sanitize import (
    is_low_content_fragment,
    is_meta_commentary,
    is_punt_phrase,
    sanitize,
)


class IsMetaCommentaryTest(unittest.TestCase):
    def test_verify_directive_is_flagged(self):
        self.assertTrue(is_meta_commentary(
            "Verify existence of 'Plan, LE1, LE2, and LE3' in the model."
        ))

    def test_consider_directive_is_flagged(self):
        self.assertTrue(is_meta_commentary(
            "Consider providing a more specific description of how 'select' is used."
        ))

    def test_remove_directive_referencing_array_index_is_flagged(self):
        self.assertTrue(is_meta_commentary(
            "Remove the duplicated entry as it is identical to glossary[15].plain_definition."
        ))

    def test_ensure_and_provide_and_add_a_are_flagged(self):
        self.assertTrue(is_meta_commentary("Ensure the field name matches the source column."))
        self.assertTrue(is_meta_commentary("Provide a more specific description here."))
        self.assertTrue(is_meta_commentary("Add a caveat about refresh timing."))

    def test_normal_prose_is_not_flagged(self):
        self.assertFalse(is_meta_commentary("Total invoiced revenue for the period in view."))
        self.assertFalse(is_meta_commentary("A field selector that switches what the chart displays."))

    def test_empty_text_is_not_flagged(self):
        self.assertFalse(is_meta_commentary(""))
        self.assertFalse(is_meta_commentary(None))

    def test_leaked_column_describer_guardrail_fragment_is_flagged(self):
        # The exact trailing clause of io.py's column-describer system
        # prompt (see io.py:354): "Only write exactly \"Unknown — requires
        # business confirmation.\" when no such structural fact is
        # available either." — reproduced verbatim, as it would appear if
        # the model echoed its own instructions into a description field.
        self.assertTrue(is_meta_commentary(
            'Only write exactly "Unknown — requires business confirmation." '
            'when no such structural fact is available either.'
        ))

    def test_orphaned_guardrail_clause_is_flagged(self):
        # The same guardrail, stranded as a dependent clause by
        # sentence-granular grounding replacement (D3) — no longer attached
        # to the sentence it was cut out of.
        self.assertTrue(is_meta_commentary("when no such structural fact is available either."))
        self.assertTrue(is_meta_commentary("when no structural fact is available either."))


class IsLowContentFragmentTest(unittest.TestCase):
    def test_short_lowercase_clause_is_flagged(self):
        self.assertTrue(is_low_content_fragment("when no such fact is available either."))

    def test_short_uppercase_sentence_is_not_flagged(self):
        # The deterministic fallback wording (D6) — short, but a real,
        # grammatically complete sentence, not stranded clause debris.
        self.assertFalse(is_low_content_fragment("No description set."))

    def test_normal_length_lowercase_fragment_is_not_flagged(self):
        self.assertFalse(is_low_content_fragment(
            "when the underlying source system records a corrected amount retroactively."
        ))

    def test_empty_text_is_not_flagged(self):
        self.assertFalse(is_low_content_fragment(""))
        self.assertFalse(is_low_content_fragment(None))


class IsPuntPhraseTest(unittest.TestCase):
    def test_column_punt_phrase_is_flagged(self):
        self.assertTrue(is_punt_phrase("Unknown — requires business confirmation."))

    def test_measure_punt_phrase_is_flagged(self):
        self.assertTrue(is_punt_phrase(
            "Business meaning could not be inferred automatically; requires business confirmation."
        ))

    def test_empty_or_none_counts_as_a_punt(self):
        self.assertTrue(is_punt_phrase(""))
        self.assertTrue(is_punt_phrase(None))

    def test_real_description_is_not_a_punt(self):
        self.assertFalse(is_punt_phrase("Key identifier; used to join Orders to related tables."))


class SanitizeTest(unittest.TestCase):
    def test_meta_commentary_falls_back(self):
        self.assertEqual(
            sanitize("Consider providing a more specific description.", "fallback text"),
            "fallback text",
        )

    def test_clean_text_passes_through(self):
        self.assertEqual(sanitize("A clean sentence.", "fallback text"), "A clean sentence.")

    def test_empty_text_falls_back(self):
        self.assertEqual(sanitize("", "fallback text"), "fallback text")
        self.assertEqual(sanitize(None, "fallback text"), "fallback text")


if __name__ == "__main__":
    unittest.main()
