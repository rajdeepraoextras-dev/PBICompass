from pathlib import Path

from pbicompass.agents.assist import ASSIST_FIELDS
from pbicompass.agents.generators import DOCUMENT_TYPES
from pbicompass.schemas.model import SemanticModel
from pbicompass.service.worker import _complete_metadata, _synchronize_glossary


FIXTURE = Path(__file__).parent / "fixtures" / "CorporateSpend" / "model.json"


class MetadataClient:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, schema, *, effort=None):
        self.calls += 1
        result = {name: "" for name in ASSIST_FIELDS}
        result.update({
            "business_decision": "Finance managers compare actual spend with plan by department.",
            "assumptions": "The uploaded model contains no source row values or tenant settings.",
            "glossary": "Actual Spend: Recorded expenditure in the selected period.",
        })
        return result


def _model():
    return SemanticModel.from_json(FIXTURE.read_text(encoding="utf-8"))


def test_ai_metadata_completion_runs_once_and_preserves_human_values():
    client = MetadataClient()
    meta = _complete_metadata(_model(), client, {"owner": "Human Owner"}, lambda _m: None)
    assert client.calls == 1
    assert meta["owner"] == "Human Owner"
    assert "actual spend" in meta["business_decision"].lower()
    assert all(meta.values())


def test_offline_metadata_uses_grounded_defaults_without_ai():
    meta = _complete_metadata(_model(), None, {}, lambda _m: None)
    assert "not identified" in meta["owner"].lower()
    assert "not stored" in meta["refresh"].lower()
    assert all(meta.values())


def test_technical_and_user_guide_share_one_canonical_glossary():
    model = _model()
    docs = {
        "technical": DOCUMENT_TYPES["technical"].generate(model, None),
        "user-guide": DOCUMENT_TYPES["user-guide"].generate(model, None),
    }
    _synchronize_glossary(docs)
    technical = [(e["term"], e["definition"]) for e in docs["technical"].glossary_entries]
    guide = [(e.term, e.plain_definition) for e in docs["user-guide"].glossary]
    assert technical == guide
    assert len({term.casefold() for term, _ in guide}) == len(guide)
