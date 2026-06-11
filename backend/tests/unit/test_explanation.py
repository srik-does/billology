"""Explanation builder: LLM path mapping + deterministic offline fallback."""

from __future__ import annotations

from src.models import Bill, BillType, LineItem, Provenance, TracedValue
from src.services.explanation import _payload, build_explanation


def _tv(v):
    return TracedValue(value=v, provenance=Provenance.extracted)


def _bill():
    return Bill(
        merchant=_tv("FreshMart"),
        bill_type=BillType.grocery,
        total_amount=_tv("160.00"),
        line_items=[
            LineItem(position=0, description=_tv("Tomatoes 1kg"), line_total=_tv("40.00")),
            LineItem(position=1, description=_tv("Milk 2L"), line_total=_tv("120.00")),
        ],
    )


class _FakeLLM:
    def explain(self, payload):
        # Echo a description per position; intentionally returns NO numbers.
        return {
            "bill_summary": "A grocery purchase.",
            "line_explanations": {"0": "Fresh tomatoes", "1": "Carton of milk"},
        }

    # Unused interface methods for this test.
    def suggest_category(self, *a, **k): ...
    def classify_question(self, *a, **k): ...
    def question_to_query(self, *a, **k): ...
    def summarize_results(self, *a, **k): ...


def test_payload_contains_no_amounts():
    payload = _payload(_bill())
    # Only descriptions are sent to the model — never amounts.
    assert all(set(li.keys()) == {"position", "description"} for li in payload["line_items"])
    assert "40.00" not in str(payload) and "120.00" not in str(payload)


def test_llm_path_maps_line_explanations_by_position():
    expl = build_explanation(_bill(), llm=_FakeLLM())
    assert expl.bill_summary == "A grocery purchase."
    assert expl.line_explanations == {"0": "Fresh tomatoes", "1": "Carton of milk"}


def test_offline_fallback_when_llm_unavailable():
    class _BoomLLM:
        def explain(self, payload):
            raise RuntimeError("no api key")

    expl = build_explanation(_bill(), llm=_BoomLLM())
    assert "FreshMart" in expl.bill_summary
    # Falls back to the extracted descriptions, keyed by position.
    assert expl.line_explanations == {"0": "Tomatoes 1kg", "1": "Milk 2L"}
