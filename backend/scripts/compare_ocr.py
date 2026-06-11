"""Prototype comparison: current Tesseract path vs RapidOCR across degradation tiers.

Usage (from repo root):
    venv\\Scripts\\python.exe backend\\scripts\\compare_ocr.py [path\\to\\real\\bill.jpg]

With no argument it synthesizes the same receipt at three degradation tiers
(clean / moderate / severe phone-photo conditions) and scores both engines
against known ground truth. Pass a real image to compare on it instead
(side-by-side output, no ground-truth scoring).

Both engines run through the production code in ``src.services.extraction.ocr``
(``_extract_rapidocr`` / ``_extract_tesseract``), so results reflect exactly
what the API would produce.
"""

from __future__ import annotations

import io
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

GROUND_TRUTH = [
    "SRI VENKATESWARA SUPER MARKET",
    "Plot 12, Gachibowli, Hyderabad",
    "GSTIN: 36AABCS1234F1Z5",
    "BILL NO: 4521   DATE: 08-06-2026",
    "ITEM           QTY    RATE     AMT",
    "RICE 5KG         1  425.00  425.00",
    "TOOR DAL 1KG     2  165.00  330.00",
    "SUNFLOWER OIL    1  142.50  142.50",
    "MILK 500ML       4   28.00  112.00",
    "ATTA 5KG         1  245.00  245.00",
    "SUBTOTAL                   1254.50",
    "CGST 2.5%                    31.36",
    "SGST 2.5%                    31.36",
    "TOTAL                      1317.22",
    "THANK YOU VISIT AGAIN",
]

KEY_TOKENS = ["VENKATESWARA", "36AABCS1234F1Z5", "425.00", "330.00", "142.50",
              "112.00", "245.00", "1254.50", "31.36", "1317.22"]

# (final width, contrast keep-factor, noise sigma, jpeg quality, rotation deg)
TIERS = {
    "clean":    (620, 0.85, 3, 85, 0.3),
    "moderate": (460, 0.70, 6, 70, 0.6),
    "severe":   (342, 0.55, 9, 55, 0.9),
}


def make_synthetic_receipt(out_path: Path, width: int, contrast: float,
                           noise: float, quality: int, rotation: float) -> None:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    font = ImageFont.truetype(r"C:\Windows\Fonts\cour.ttf", 22)
    line_h = 30
    pad = 24
    base_w = 620
    sep = "-" * 36
    body = GROUND_TRUTH[:3] + [sep] + GROUND_TRUTH[3:4] + [sep] + GROUND_TRUTH[4:10] \
        + [sep] + GROUND_TRUTH[10:14] + [sep] + GROUND_TRUTH[14:]
    img = Image.new("L", (base_w, pad * 2 + line_h * len(body)), 235)
    draw = ImageDraw.Draw(img)
    y = pad
    for line in body:
        draw.text((pad, y), line, font=font, fill=70)  # thermal print: dark grey
        y += line_h

    img = img.rotate(rotation, expand=False, fillcolor=235, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    arr = np.asarray(img, dtype=np.float32)
    arr = 140 + (arr - 140) * contrast
    rng = np.random.default_rng(42)
    arr += rng.normal(0, noise, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "L")
    if width < img.width:
        img = img.resize((width, round(img.height * width / img.width)), Image.BILINEAR)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    out_path.write_bytes(buf.getvalue())


def _run_engine(extract_fn, image_bytes: bytes):
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes))
    t0 = time.perf_counter()
    result = extract_fn(image)
    elapsed = time.perf_counter() - t0
    return [(l.text, l.confidence) for l in result.lines], result.confidence, elapsed


def run_tesseract(image_bytes: bytes):
    from src.services.extraction.ocr import _extract_tesseract

    return _run_engine(_extract_tesseract, image_bytes)


def run_rapidocr(image_bytes: bytes):
    from src.services.extraction.ocr import _extract_rapidocr

    return _run_engine(_extract_rapidocr, image_bytes)


def normalize(s: str) -> str:
    return " ".join(s.upper().split())


def score(lines: list[tuple[str, float]]):
    # Space-insensitive: detector-based engines segment words differently,
    # which shouldn't count as character errors.
    got = normalize(" ".join(t for t, _ in lines)).replace(" ", "")
    truth = normalize(" ".join(GROUND_TRUTH)).replace(" ", "")
    # autojunk=False: on long strings the default heuristic junks frequent
    # characters and wildly understates similarity.
    sim = SequenceMatcher(None, truth, got, autojunk=False).ratio()
    hits = sum(1 for tok in KEY_TOKENS if tok in got)
    missed = [tok for tok in KEY_TOKENS if tok not in got]
    return sim, hits, missed


# rapidocr must run first: creating its ONNX sessions after a pytesseract
# subprocess call leaves them ~10x slower for the whole process (measured
# 18s vs 1.7s per receipt). In production, create the engine at startup.
ENGINES = [("rapidocr", run_rapidocr), ("tesseract", run_tesseract)]


def main() -> None:
    if len(sys.argv) > 1:
        image_bytes = Path(sys.argv[1]).read_bytes()
        for label, runner in ENGINES:
            lines, conf, elapsed = runner(image_bytes)
            print(f"=== {label} ===  conf {conf:.2f}  time {elapsed:.2f}s")
            for text, line_conf in lines:
                print(f"  [{line_conf:.2f}] {text}")
            print()
        return

    summary = []
    for tier, (width, contrast, noise, quality, rotation) in TIERS.items():
        path = BACKEND_DIR / "scripts" / f"_sample_receipt_{tier}.jpg"
        make_synthetic_receipt(path, width, contrast, noise, quality, rotation)
        image_bytes = path.read_bytes()
        print(f"########## {tier.upper()} ({width}px wide) ##########")
        for label, runner in ENGINES:
            lines, conf, elapsed = runner(image_bytes)
            sim, hits, missed = score(lines)
            summary.append((tier, label, sim, hits, conf, elapsed))
            print(f"--- {label}: key tokens {hits}/{len(KEY_TOKENS)}, char sim {sim:.1%}, "
                  f"conf {conf:.2f}, {elapsed:.2f}s"
                  + (f", missed: {', '.join(missed)}" if missed else ""))
            for text, line_conf in lines:
                print(f"  [{line_conf:.2f}] {text}")
        print()

    print("########## SUMMARY ##########")
    print(f"{'tier':<10} {'engine':<10} {'tokens':>7} {'charsim':>8} {'conf':>5} {'time':>6}")
    for tier, label, sim, hits, conf, elapsed in summary:
        print(f"{tier:<10} {label:<10} {hits:>4}/{len(KEY_TOKENS)} {sim:>7.1%} {conf:>5.2f} {elapsed:>5.2f}s")


if __name__ == "__main__":
    main()
