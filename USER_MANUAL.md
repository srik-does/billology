# Billology — User Manual

**Billology reads a bill, checks its arithmetic, explains every charge in plain
language, and answers questions about your spending — and it never invents a
number.** If it can't read something, it tells you honestly instead of guessing.

- **Live web demo:** <https://billology.onrender.com>
- **Android app (APK):** download from the latest
  [GitLab Release](https://code.swecha.org/srikeerthan_reddy/billology/-/releases)

> The hosted backend runs on a free tier. After a period of inactivity, the
> first request may take ~30 seconds while the server wakes up. This is normal.

---

## 1. Getting started

### On Android (recommended)

1. Open the latest [GitLab Release](https://code.swecha.org/srikeerthan_reddy/billology/-/releases)
   and download **`billology.apk`** from the **Assets** section.
2. Open the downloaded file on your phone and tap **Install**. If prompted,
   enable **"Install unknown apps"** for your browser or file manager
   (Settings → Apps → Special access → Install unknown apps).
3. Launch **Billology** and grant the camera/photo permission when asked.

The app is preconfigured to talk to the hosted backend, so there is nothing to
set up. Requires **Android 6.0+**. (This is an unsigned preview build meant for
side-load distribution.)

### In a web browser

Just open <https://billology.onrender.com>. No install required.

---

## 2. Submitting a bill

You can submit a bill three ways:

| Method | Best for |
|---|---|
| **Photo** | A paper receipt or an on-screen bill. Fill the frame, keep it flat and well-lit. |
| **PDF** | Emailed invoices and statements (both digital PDFs and fully scanned ones). |
| **Pasted text** | A bill you can copy as text (e.g. an SMS or email body). |

Tips for the best photo results:

- Lay the receipt flat; avoid folds, glare, and shadows.
- Capture the whole bill, including the totals section.
- Sharper is better — let the camera focus before you shoot.

After you submit, Billology extracts the merchant, line items, taxes, and
totals, then runs its checks. This takes a few seconds.

---

## 3. Reading the results

### Extracted bill

You'll see the merchant, date, individual line items, taxes/charges, and the
total — exactly as printed. Each figure is copied from your bill and
re-checked by the app; anything it couldn't read reliably is left blank rather
than filled in with a guess.

### Verification (the arithmetic check)

Billology independently re-adds the bill and flags **provable** problems, showing
you the conflicting numbers as evidence:

- **Sum mismatch** — the line items don't add up to the stated total.
- **Duplicate charge** — the same item appears to be billed twice.
- **Tax error** — the tax figure is inconsistent with the amounts.

It deliberately does **not** flag legitimate layouts where things don't naively
sum — for example discounts, rounding, or tax-inclusive pricing. No warning
means nothing provably wrong was found; it is not a guarantee, so a quick glance
is still worthwhile.

### Explanations

Alongside the figures (never replacing them), you get a plain-language summary of
the bill and, where helpful, an explanation of individual charges. These are
descriptions of numbers already extracted — the amounts themselves always come
from your bill.

### Category

Billology suggests a spending category (e.g. Groceries, Dining, Utilities). You
can change it before saving.

---

## 4. Reviewing and saving

Before saving, you can **correct any field** — a misread amount, a wrong
merchant name, the date, or the category. Fields you edit are marked as
**user-provided** so it's clear which values came from you versus from the bill.

Tap **Save** to store the bill in your history.

---

## 5. History

From your history you can:

- **List** all saved bills.
- **Search** by merchant name.
- **Filter** by category.
- **Delete** a single bill, or **clear all**.

---

## 6. Spending dashboard

The dashboard summarizes your saved bills:

- **By category** — where your money goes.
- **By month** — how spending trends over time.

These totals are computed directly from your saved bills.

---

## 7. Ask (natural-language questions)

Ask questions about your spending in plain English, for example:

- "How much did I spend on groceries last month?"
- "What was my biggest bill in June?"
- "Show me everything from BigBazaar."

Two kinds of questions are handled:

- **Numeric** ("how much…") — the app computes the answer from your actual saved
  bills. The figure is always calculated in code, never estimated.
- **Descriptive** ("show me…", "what about…") — the app retrieves the most
  relevant bills and summarizes them.

If an answer can't be determined from your data, Billology says so explicitly
rather than making something up.

---

## 8. Privacy

- You sign in with Google; your bills are stored privately and are visible only
  to you (enforced at the database level).
- **Bill images are sent to the configured AI provider (Groq by default) for
  reading (transcription).** This is a deliberate, documented trade-off for
  extraction accuracy. Self-hosters can turn this off (`VISION_EXTRACTION=false`
  for local-only OCR) or use a local provider — see the README.
- See [`SECURITY.md`](SECURITY.md) and [`COMPLIANCE.md`](COMPLIANCE.md) for
  details.

---

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| First request is very slow (~30 s) | The free-tier backend is waking up. Wait and retry. |
| "Couldn't read" the bill | Retake the photo flatter, brighter, and in sharper focus; or paste the text / upload a PDF instead. |
| A number looks wrong | Correct it in the review screen before saving — your edit is marked as user-provided. |
| App can't reach the server | Check your internet connection and try again. |
| Installing the APK is blocked | Enable "Install unknown apps" for your browser/file manager, then reopen the file. |

For anything else, or to report a bug, see [`CONTRIBUTING.md`](CONTRIBUTING.md).
