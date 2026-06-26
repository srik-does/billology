# Billology — User Growth & Continuous Improvement Strategy

_How we plan to grow the user base, and how we continuously improve features and
functionality based on real usage._

> **Scope.** This document answers two linked questions:
> 1. How do we plan to increase the user base?
> 2. How do we continuously improve functionality, features, and (through that) grow retention and the user base?
>
> It is a living document. Update it at the end of every growth cycle (see the
> review cadence at the bottom).

---

## 1. Where we are today (baseline)

| Item | Current state | Source |
|---|---|---|
| Product | AI bill analyzer: capture (photo / PDF / pasted text) → extract → verify arithmetic → explain → save → ask | `README.md` |
| Platforms live | Android app (Expo / EAS, distributed as APK) + web app served by the backend at `/` | `mobile/`, `backend/src/web/index.html` |
| Live deployment | <https://billology.onrender.com> (API docs at `/docs`) | `render.yaml` |
| Languages | 13-language UI (English + 12 Indian languages); LLM explanations and Q&A localized | `mobile/src/i18n.ts`, `backend/src/services/llm_service.py` |
| Feedback channel | Beta review form (Google Form generator) | `feedback/create_review_form.gs` |
| Registered users | Not yet tracked — **establishing measurement is Week 1 work** | — |

We are at the **beta / first-users** stage. The goal of the first cycle is not
vanity numbers but a **repeatable loop**: get real users → measure what they do →
fix the top friction → bring the next, larger cohort.

---

## 2. Target users & the value we lead with

| Persona | Pain we solve | Hook |
|---|---|---|
| Budget-conscious individuals / students | "Where did my money go this month?" | Snap a bill → instant categorized spending dashboard |
| Small-shop / kirana customers, families | GST/total errors, unreadable receipts | "Billology checks the arithmetic and never invents a number" |
| Regional-language users | English-only finance apps exclude them | Full UI + answers in Hindi, Telugu, Tamil, and 9 more |
| Privacy-cautious users | "Where do my bills go?" | Local-only mode (Ollama / OCR), private storage, AGPL/open source |

**Positioning line:** _"Photograph any bill — Billology reads it, checks it, and
explains your spending, in your language. The numbers always come from the bill,
never the AI."_

---

## 3. Growth model

We grow on three reinforcing engines, in priority order:

1. **Community / institutional distribution (primary).** Billology originates in
   the Swecha free-software ecosystem (`code.swecha.org`). Colleges, FOSS clubs,
   and student communities are our cheapest, highest-trust channel.
2. **Word-of-mouth via a genuinely useful free tool.** Open source + no cost +
   "it caught an error on my bill" is shareable. We instrument referral moments.
3. **Content & search.** Plain-language explainers ("how to read a GST bill",
   "track grocery spend") in English and Indic languages, linking to the web app.

Paid acquisition is explicitly **out of scope** until retention (below) is proven.

---

## 4. Week-by-week plan (12-week cycle)

> Each week has a **goal**, a **growth action**, and a **product/quality action**,
> because acquisition without functional improvement just leaks users faster.

### Phase A — Instrument & harden (Weeks 1–3)
| Week | Growth action | Product / quality action | Success signal |
|---|---|---|---|
| 1 | Stand up **measurement**: anonymous event logging (signups, bills scanned, extraction success/failure, Q&A used, language chosen). Define the funnel. | Add a lightweight metrics/event sink behind the existing auth; document opt-out in `PRIVACY.md`. | We can read a daily funnel. |
| 2 | Recruit a **closed pilot of ~20–30 users** from one college / FOSS club. Hand out the APK + web link + the beta review form. | Triage the top 5 extraction-failure bill types from pilot uploads; fix the worst. | ≥20 active pilot users; first failure backlog. |
| 3 | 1:1 / small-group feedback calls with pilot users. | Ship fixes for the top friction (sign-in, slow first scan warm-up, wrong totals). | Extraction success rate +; sign-in complaints ↓. |

### Phase B — First public cohort (Weeks 4–7)
| Week | Growth action | Product / quality action | Success signal |
|---|---|---|---|
| 4 | **Public soft launch** to 2–3 communities (campus groups, r/india-style finance subs, FOSS mailing lists). Publish a short demo video + README screenshots. | Add screenshots/GIFs to README; cross-browser smoke test (Chrome/Firefox/Safari/Edge) for the web client. | First organic signups outside pilot. |
| 5 | Launch **content track**: 2 explainer posts (1 English, 1 Indic) linking to the web app. | Improve Indic UI quality: get native-speaker review for the 10 machine-authored languages flagged in `i18n.ts`. | Inbound traffic from content; Indic UI corrections merged. |
| 6 | Activate **referral moment**: after a user's first successful save, prompt "share Billology". | Build the share/deeplink; reduce time-to-first-value (warm-up, onboarding hints). | Referral shares > 0; faster first-scan. |
| 7 | Outreach to **2 new institutions / regions** with localized messaging. | Add the most-requested feature from Phase A/B feedback (e.g. export, more bill types). | New cohort onboarded; feature ships. |

### Phase C — Retention & scale (Weeks 8–12)
| Week | Growth action | Product / quality action | Success signal |
|---|---|---|---|
| 8 | Re-engagement: monthly "your spending summary" nudge to returning users. | Dashboard / Q&A quality pass driven by usage data. | WAU/MAU trending up. |
| 9 | **Contributor funnel** (feeds the product engine): publish good-first-issues, point new contributors at translations and parsers. See `contributor-growth.md`. | Convert top community feature requests into issues. | First external contributions. |
| 10 | Expand to the next geography/language tier — coordinate with `geographical-expansion.md`. | Low-bandwidth / low-end device pass (asset size, lazy loading). | App usable on entry-level phones / 3G. |
| 11 | Partnerships: pitch a campus finance-literacy workshop using Billology. | Stability hardening; close the bug backlog. | Crash/error rate ↓. |
| 12 | **Cycle review** — publish results, set targets for the next 12 weeks. | Roadmap update from the cycle's learnings. | Documented next-cycle plan. |

---

## 5. The continuous-improvement loop (how features keep getting better)

Growth and product quality are one loop, run every cycle:

```
   Acquire a cohort
        │
        ▼
   Measure behaviour  ──►  events: scans, extraction success/fail,
        │                  Q&A use, language, drop-off points
        ▼
   Collect feedback   ──►  in-app beta review form + 1:1 calls
        │                  (feedback/create_review_form.gs)
        ▼
   Prioritize         ──►  rank by (frequency × severity); the
        │                  "LLM never invents a number" rule is fixed
        ▼
   Ship improvement   ──►  spec under specs/ → PR → CI (lint/type/
        │                  test/security) → release (CHANGELOG via git-cliff)
        ▼
   Verify on real users ─► metrics move? feedback resolved?
        │
        └──────────────► next, larger cohort
```

**Concrete mechanisms already in the repo we build on:**
- **Feedback capture:** `feedback/create_review_form.gs` (extraction accuracy,
  sign-in, speed, language, bugs, NPS-style "keep using" score).
- **Quality gates so improvements don't regress:** CI pipeline (`.gitlab-ci.yml`)
  runs ruff, mypy, pytest+coverage, gitleaks, pip-audit, npm-audit; changelog is
  generated from conventional commits (`cliff.toml`, `CHANGELOG.md`).
- **Spec-driven changes:** every behavior change updates a spec under `specs/`,
  keeping functionality documented as it grows.

**What we will add to close the loop (tracked as Week 1–2 tasks):**
- Anonymous, consent-based **usage analytics** (extraction success rate is the
  north-star quality metric).
- A public **roadmap / changelog** so users see their feedback turn into features.

---

## 6. Metrics we steer by

| Layer | Metric | Why it matters |
|---|---|---|
| Acquisition | New signups / week, by channel | Which channel actually works |
| Activation | % of new users who save ≥1 bill | First value delivered |
| **Quality (north star)** | **Extraction success rate** (bills that produce a usable, correct total) | The product's core promise |
| Engagement | Bills scanned / active user; Q&A and dashboard usage | Habit forming |
| Retention | W1 / W4 return rate; WAU/MAU | Real growth vs. leaky bucket |
| Inclusion | Share of non-English sessions | Are we reaching Indic users |
| Advocacy | Referral shares; "likely to keep using" score | Word-of-mouth potential |

A growth action is only "successful" if it improves activation/retention, not
just raw signups.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Cold-start latency on free hosting (first scan slow) | Documented to users; evaluate keep-warm / lighter tier as usage justifies |
| Extraction errors erode trust | North-star metric + fast fix loop; honest "couldn't read" instead of fabrication (already a design rule) |
| Machine-translated Indic UI feels off | Native-speaker review track (Phase B); corrections are single-file PRs |
| Privacy concerns block adoption | Local-only mode, private storage, `PRIVACY.md`, open source |
| Growth outpaces capacity | Gate paid/scaled outreach behind proven retention |

---

## 8. Review cadence

- **Weekly:** funnel + top-feedback review (15 min); adjust the next week's actions.
- **End of each 12-week cycle:** publish results, refresh this document and the
  roadmap, set the next cycle's targets.
- **Owners:** maintainer(s) listed in `CONTRIBUTING.md`; community leads per region
  (see `geographical-expansion.md`).

_Related: [`geographical-expansion.md`](geographical-expansion.md) (reach &
onboarding), [`contributor-growth.md`](contributor-growth.md) (contributor funnel,
to be added)._
