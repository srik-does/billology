from src.models import BillType

from .inr import parse_inr

__all__ = ["parse_inr", "detect_bill_type"]


def detect_bill_type(raw_text: str) -> BillType:
    """Keyword-based bill-type detection over extracted/transcribed text.

    Shared by the deterministic pipeline and the vision path (used there only
    when the model's own type claim fails validation).
    """
    from src.services.parsers import grocery, telecom

    low = raw_text.lower()

    # Strong signals are decisive (telecom checked first: a recharge bill is
    # unambiguously telecom even if it carries generic invoice vocabulary).
    if any(kw in low for kw in telecom.STRONG):
        return BillType.telecom_recharge
    if any(kw in low for kw in grocery.STRONG):
        return BillType.grocery

    # Otherwise fall back to weighted keyword counts.
    telecom_hits = sum(1 for kw in telecom.KEYWORDS if kw in low)
    grocery_hits = sum(1 for kw in grocery.KEYWORDS if kw in low)
    if telecom_hits == 0 and grocery_hits == 0:
        return BillType.unsupported
    return BillType.telecom_recharge if telecom_hits >= grocery_hits else BillType.grocery
