# Billology — Reach Expansion & User Onboarding (Geographical / Horizontal)

_How we expand reach and onboard users across regions — horizontal geographic
expansion — without losing the product's core promise that figures always come
from the bill, never the model._

> **Scope.** This document answers:
> 1. How do we expand our reach and onboard users?
> 2. How do we expand horizontally / geographically into new regions?
>
> Read alongside [`growth-strategy.md`](growth-strategy.md), which covers the
> overall user-growth engine and week-by-week plan. This document is specifically
> about **place and language** — taking the product to a new region and getting its
> users productive.

---

## 1. Why geographic/horizontal expansion fits Billology

Billology is already built to travel across India:

| Built-in lever | Evidence | Why it helps expansion |
|---|---|---|
| **13-language UI** (English + Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Odia, Assamese, Urdu) | `mobile/src/i18n.ts`, `llm_service.py` `_LANG_NAMES` | A new linguistic region can use the app in its language on day one |
| **Localized LLM output** via `X-Language` header | `backend/src/services/llm_service.py` | Explanations and Q&A answer in the user's language |
| **INR / GST-aware extraction** and regional terms (e.g. "kirana") | `backend/src/services/parsers/`, `llm_service.py` enrich prompts | Indian bill formats are first-class, region to region |
| **Low-footprint clients** (Expo Android APK + backend-served web) | `mobile/`, `backend/src/web/index.html` | Easy to distribute where app-store reach or bandwidth is limited |
| **Local-only / BYO-key AI mode** (Ollama / OCR fallback) | `llm_service.py` (`OllamaLLMService`) | Works in privacy- or connectivity-constrained settings |
| **Open source (AGPL)** + Swecha origin | `LICENSE`, `code.swecha.org` remote | Community partners in each region can host, translate, and advocate |

"Horizontal expansion" for us means **the same product reaching the next
geography and language tier** — not new product lines.

---

## 2. Expansion principles

1. **Language before geography.** A region adopts only if the app speaks its
   language well. We verify native-speaker-reviewed UI + a real bill sample set
   before promoting a region.
2. **Local anchor, not parachute.** Each region launches through a local
   community lead (FOSS club, college, Swecha chapter) — not remote marketing.
3. **Prove the bills extract correctly first.** Bill layouts vary by state and
   merchant. We validate extraction on real regional bills before public push.
4. **Onboarding in-context.** First-run help, the camera flow, and the "couldn't
   read — try again / fix it" path must be understandable with zero training.
5. **Measure per region.** Adoption, extraction success, and language mix are
   tracked per region so we expand where it works.

---

## 3. Expansion tiers (where we go, in order)

| Tier | Region focus | Primary language(s) | Rationale |
|---|---|---|---|
| **Tier 0 — Home** | Telangana / Hyderabad (Swecha home) | Telugu, English, Urdu | Origin community; tightest feedback loop |
| **Tier 1 — Reviewed Indic** | Regions for the human-reviewed languages | Hindi, Telugu (already reviewed) | UI is already trustworthy here |
| **Tier 2 — South + West** | Tamil Nadu, Karnataka, Kerala, Maharashtra, Gujarat | Tamil, Kannada, Malayalam, Marathi, Gujarati | High smartphone + receipt density; languages shipped, pending native review |
| **Tier 3 — East + North** | West Bengal, Punjab, Odisha, Assam, Hindi belt | Bengali, Punjabi, Odia, Assamese, Hindi | Completes the 12-language coverage |
| **Tier 4 — Diaspora / non-INR (future)** | Indian diaspora; later, other currencies | English + above | Requires multi-currency work (see §7) |

Each tier only "opens" after the previous tier's **region-readiness checklist**
(below) passes.

---

## 4. Region-readiness checklist (gate before launching a region)

A region is ready to onboard the public when **all** are true:

- [ ] **Language reviewed** — the region's UI strings in `mobile/src/i18n.ts` are
      reviewed by a native speaker (the 10 machine-authored languages are flagged
      for exactly this in `i18n.ts`). Corrections merged.
- [ ] **Bill sample tested** — ≥20 real bills from that region (grocery, telecom,
      utility, restaurant) run through extraction; success rate measured and the
      top failure types fixed or known.
- [ ] **Local anchor identified** — a community lead / club / institution committed
      to host the first cohort.
- [ ] **Localized onboarding** — first-run help and the demo video exist in the
      region's primary language.
- [ ] **Support path** — a feedback channel (the beta review form, localized) and
      a contact for that region.
- [ ] **Metrics wired** — per-region tagging so we can read adoption and extraction
      success for that region.

---

## 5. Per-region launch playbook (repeatable)

Run this for each new region; target ~3–4 weeks per region.

**Week 1 — Localize & validate**
- Finalize native-speaker UI review for the region's language.
- Collect a regional bill sample; run the extraction test; fix top failures.
- Translate onboarding (first-run help, one-page "how it works", demo clip).

**Week 2 — Anchor & pilot**
- Onboard a **closed pilot (15–30 users)** via the local anchor (campus/club).
- Distribute: Android APK (EAS build) + web link <https://billology.onrender.com>.
- Walk pilot users through capture → review → save → ask in their language.

**Week 3 — Feedback & fix**
- 1:1 / group feedback; collect the localized beta review form responses.
- Fix the top friction (extraction, sign-in, speed, mistranslations).

**Week 4 — Public open + handoff**
- Open to the broader community in that region; publish localized content.
- Hand ongoing community management to the local lead; keep measuring.
- Decide go/no-go to open the next region.

---

## 6. How users get onboarded (the user-facing path)

The app is designed so a first-time user in any supported region succeeds without
training:

1. **Get the app** — install the Android APK or open the web app in a browser
   (no install). Both point at the same backend.
2. **Choose language** — Settings exposes all 13 languages; LLM explanations and
   Q&A follow the choice (`X-Language`).
3. **Sign in** — Google sign-in (one tap), with an in-app privacy note that bills
   are visible only to the user.
4. **First bill** — guided capture (photo of each page, image/PDF pick, or paste
   text). The Help screen (`HelpScreen.tsx`) explains the four steps.
5. **See value immediately** — extraction + arithmetic check + plain-language
   explanation; on a bad read the app says "couldn't read — retry or fix it"
   rather than guessing.
6. **Habit** — dashboard (spending by category / month) and "Ask" answer questions
   in the user's language, from their own saved bills only.

Onboarding friction we explicitly track and reduce per region: sign-in success,
time-to-first-successful-scan, and first-scan warm-up latency on free hosting.

---

## 7. Deeper expansion (beyond UI translation)

Horizontal expansion eventually needs more than language toggles. Tracked as
roadmap items, opened per tier:

| Need | Why | Status |
|---|---|---|
| **Regional bill-format coverage** | State/merchant layouts differ (GST summaries, telecom recharges, electricity bills) | Parsers + vision prompts extended per region from the sample sets |
| **Native-speaker UI review** for 10 languages | Machine-authored strings need polishing | Flagged in `i18n.ts`; Tier 2–3 gates |
| **Low-bandwidth / low-end device mode** | Rural and entry-level-phone reach | See `growth-strategy.md` Phase C; asset/lazy-load pass |
| **Offline / local-only resilience** | Connectivity-constrained regions | Local Ollama/OCR mode exists; document and test |
| **Multi-currency** (Tier 4) | Diaspora / non-INR bills | Future; extraction is INR-centric today |
| **Localized content & support** | Discovery + trust in-region | Per-region in the launch playbook |

---

## 8. Metrics per region

| Metric | What it tells us |
|---|---|
| Signups & active users in region | Is the anchor working |
| **Extraction success rate on regional bills** | Does the product actually work there (gate metric) |
| Share of sessions in the regional language | Is localization landing |
| Time-to-first-successful-scan | Onboarding friction |
| Retention (W1/W4) in region | Worth deepening investment |

A region graduates from "pilot" to "open" only when extraction success and W1
retention clear the bar set for the previous tier.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Translation quality varies (machine-authored languages) | Native-speaker review gate before public launch; single-file PR corrections |
| Regional bill formats break extraction | Sample-test gate; per-region parser/prompt tuning; honest failure UX |
| No local anchor → cold launch flops | Don't open a region without a committed local lead |
| Connectivity/cost barriers | Web (no install) + low-bandwidth pass + local-only AI mode |
| Spreading too thin across regions | Strict tier ordering; one region opens only after the prior tier's checklist passes |

---

## 10. Review cadence

- **Per region:** go/no-go review at the end of each 4-week launch playbook.
- **Per tier:** open the next tier only after the current tier's readiness
  checklist and metrics pass.
- **Owners:** maintainer(s) (`CONTRIBUTING.md`) + a named local lead per region.

_Related: [`growth-strategy.md`](growth-strategy.md) (overall growth engine &
week-wise plan), [`contributor-growth.md`](contributor-growth.md) (contributor
expansion across institutions, to be added)._
