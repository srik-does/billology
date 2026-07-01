"""Telecom / recharge-provider bill parser.

Shares the deterministic core in ``base.parse``; telecom bills are typically a
small number of charges (plan amount, taxes) plus a total/amount-payable line.
"""

from __future__ import annotations

from src.models import Bill, BillType
from src.services.extraction.types import ExtractionResult
from src.services.parsers import base

# Hints used by the orchestrator's bill-type detection.
KEYWORDS = (
    "recharge",
    "validity",
    "talktime",
    "plan",
    "data",
    "operator",
    "mobile number",
    "prepaid",
    "postpaid",
    "airtel",
    "jio",
    "vi ",
    "vodafone",
    "bsnl",
)

# Decisive signals: if any appear, the bill is telecom regardless of generic
# invoice vocabulary it may share with grocery receipts.
STRONG = (
    "recharge",
    "talktime",
    "validity",
    "prepaid",
    "postpaid",
    "data pack",
    "mobile number",
    "operator",
    "airtel",
    "jio",
    "vodafone",
    "bsnl",
)


def parse(result: ExtractionResult) -> Bill:
    return base.parse(result, BillType.telecom_recharge)
