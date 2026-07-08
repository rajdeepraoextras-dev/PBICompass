"""Deterministic output-sanitation guards (AI-Native roadmap D2/D6).

Two small, pure-Python checks that protect user-facing prose from two
distinct LLM failure modes seen in production output:

- :func:`is_meta_commentary` (D2) — the model occasionally returns an
  internal editing directive or a reference to the document's own data
  structures instead of the content a field asked for, e.g. "Consider
  providing a more specific description of how 'select' is used" shipped
  as a glossary definition, or "Remove the duplicated entry as it is
  identical to glossary[15].plain_definition." Neither is a factual claim,
  so the grounding pass (Phase 3) never catches it — this is a cheaper,
  earlier, deterministic net.
- :func:`is_punt_phrase` (D6) — the model's own "I don't know" sentences
  ("Unknown — requires business confirmation.", "Business meaning could
  not be inferred automatically; requires business confirmation."). Used
  by callers to enforce "the LLM may only improve, never downgrade": a
  punt is never allowed to overwrite an existing, real deterministic
  description.

Both are guards a caller applies at the merge point where an LLM result
would otherwise overwrite a value already computed elsewhere — neither
function invents replacement text; callers always fall back to whatever
deterministic/prior text they already had.
"""

from __future__ import annotations

import re
from typing import Optional

_STARTS_WITH_DIRECTIVE = re.compile(
    r"^\s*(Consider|Remove|Verify|Ensure|Add a|Provide)\b", re.IGNORECASE
)
_META_REFERENCE = re.compile(
    r"glossary\[|plain_definition|the duplicated entry", re.IGNORECASE
)


def is_meta_commentary(text: Optional[str]) -> bool:
    """True when ``text`` reads like an internal editing directive or a
    reference to the document's own data structures rather than actual
    prose (D2)."""
    if not text:
        return False
    return bool(_STARTS_WITH_DIRECTIVE.search(text) or _META_REFERENCE.search(text))


def is_punt_phrase(text: Optional[str]) -> bool:
    """True when ``text`` is empty or one of the established "I don't
    know" sentences (D6) — used to stop the LLM from downgrading a good
    deterministic/prior description to a punt."""
    if not text:
        return True
    return "requires business confirmation" in text.lower()


def sanitize(text: Optional[str], fallback: str) -> str:
    """Return ``text`` unless it is meta-commentary (D2), in which case
    fall back to ``fallback`` — the deterministic or prior-good text."""
    if text and not is_meta_commentary(text):
        return text
    return fallback
