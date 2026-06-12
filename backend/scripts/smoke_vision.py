"""One-shot smoke test for v2 vision extraction against the real provider.

Renders a synthetic receipt (so no real bill data is needed), runs it through
``process_inputs``, and prints the structured result. Pass a real image path
as the first argument to test with an actual bill photo instead.

Run from repo root:  venv\\Scripts\\python.exe backend\\scripts\\smoke_vision.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

RECEIPT = [
    "SRI BALAJI SUPERMARKET",
    "MG Road, Vijayawada",
    "Date: 10/06/2026  Bill No: 4821",
    "--------------------------------",
    "Rice 5kg          1   425.00",
    "Toor Dal 1kg      2   180.00",
    "Sunflower Oil 1L  1   142.00",
    "--------------------------------",
    "Sub Total             747.00",
    "CGST 2.5%              18.68",
    "SGST 2.5%              18.68",
    "Total              Rs 784.36",
    "Thank you! Visit again",
]


def _synthetic_receipt() -> bytes:
    img = Image.new("RGB", (420, 40 + 30 * len(RECEIPT)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(RECEIPT):
        draw.text((20, 20 + 30 * i), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main() -> None:
    from src.services.extraction import process_inputs

    sys.stdout.reconfigure(encoding="utf-8")  # transcripts may carry ₹ etc.

    if len(sys.argv) > 1:
        payload = (Path(sys.argv[1]).read_bytes(), Path(sys.argv[1]).name, "image/jpeg")
    else:
        payload = (_synthetic_receipt(), "receipt.png", "image/png")

    bill = process_inputs(files=[payload])
    print(bill.model_dump_json(indent=2, exclude_none=True))


if __name__ == "__main__":
    main()
