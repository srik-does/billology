"""Indian-locale money parsing.

Parses tokens like ``₹1,00,000``, ``Rs. 1,23,456.78``, ``INR 250`` into an exact
``Decimal``. The Decimal is built from the cleaned *string* (never via float), so
no binary-floating-point error is introduced before arithmetic (Principle I).

Indian grouping (lakh/crore: 1,00,000) differs from Western thousands grouping,
but since we simply strip *all* group separators the grouping style is irrelevant
to the numeric result — both ``1,00,000`` and ``100,000`` yield Decimal('100000').
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Match currency markers including a trailing dot (e.g. "Rs.") so no stray
# separator is left behind. No \b anchors — they would let "Rs." match as "Rs"
# and leave a dangling ".".
_CURRENCY = re.compile(r"(?i)rs\.?|inr|₹")
_ALLOWED = re.compile(r"[^0-9.\-]")


class INRParseError(ValueError):
    """Raised when a token cannot be parsed as an INR amount."""


def parse_inr(token: str) -> Decimal:
    """Parse an INR-formatted token into an exact Decimal.

    Raises INRParseError if the token contains no parseable number.
    """
    if token is None:
        raise INRParseError("cannot parse None as INR amount")

    s = token.strip()
    # Parenthesised negatives, e.g. "(1,200.00)"
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]

    s = _CURRENCY.sub("", s)
    # Remove every non-digit/dot/minus char (this drops all comma group separators).
    s = _ALLOWED.sub("", s).strip()

    if s in ("", "-", ".", "-."):
        raise INRParseError(f"no number found in token: {token!r}")

    try:
        value = Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise INRParseError(f"invalid INR amount: {token!r}") from exc

    return -value if negative else value
