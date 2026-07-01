"""Printed grocery-receipt parser.

Shares the deterministic core in ``base.parse``; grocery receipts are typically
many item lines (description + amount) plus subtotal/tax/total lines.
"""

from __future__ import annotations

from src.models import Bill, BillType
from src.services.extraction.types import ExtractionResult
from src.services.parsers import base

# Hints used by the orchestrator's bill-type detection. Cross-cutting invoice
# vocabulary (invoice/bill no/hsn) is intentionally excluded — telecom GST
# invoices carry those too and they were causing misclassification.
KEYWORDS = (
    "qty",
    "mrp",
    "item",
    "cashier",
    "kg",
    "pcs",
    "supermarket",
    "mart",
    "store",
    "grocery",
)

# Decisive grocery signals.
STRONG = ("mrp", "qty", "cashier", "supermarket", "grocery")


def parse(result: ExtractionResult) -> Bill:
    return base.parse(result, BillType.grocery)
