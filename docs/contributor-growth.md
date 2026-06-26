# Billology — Contributor Growth & Community Strategy

_How we grow the contributor base, onboard new contributors, and expand the
community across institutions and regions — so the product's improvement engine
(see [`growth-strategy.md`](growth-strategy.md)) has the people to power it._

> **Scope.** This document answers:
> 1. How do we attract and onboard new contributors?
> 2. How do we expand the contributor base horizontally — across colleges,
>    communities, and regions?
>
> Read alongside [`growth-strategy.md`](growth-strategy.md) (user growth) and
> [`geographical-expansion.md`](geographical-expansion.md) (regional reach).
> Contributor growth and user growth reinforce each other: more users surface more
> regional bills and translations; more contributors fix them faster.

---

## 1. Why contributors fit Billology

| Built-in lever | Evidence | Why it lowers the contribution barrier |
|---|---|---|
| **Open source (AGPL)** + Swecha origin | `LICENSE`, `code.swecha.org` remote | A welcoming FOSS-community home and audience |
| **Spec-driven codebase** | `specs/`, `.specify/`, `CONTRIBUTING.md` | New contributors read the spec to understand intent before touching code |
| **One clear, principled rule** | `CONTRIBUTING.md` ("the LLM never produces numbers") | Easy to know what a "good" change looks like |
| **Translations are single-file PRs** | `mobile/src/i18n.ts` (10 languages flagged for native review) | Non-coders and language speakers can contribute immediately |
| **Strong quality gates** | `.gitlab-ci.yml` (ruff, mypy, pytest+coverage, gitleaks, audits) | Contributors get fast, automated feedback; maintainers can say yes safely |
| **Conventional commits + changelog automation** | `cliff.toml`, `CHANGELOG.md` | Predictable, low-friction contribution mechanics |

The cheapest, highest-trust contributor channel is the same as our user channel:
**colleges, FOSS clubs, and Swecha chapters**.

---

## 2. Contribution on-ramps (something for everyone)

We deliberately offer graduated entry points so a first contribution is small and
high-confidence:

| On-ramp | Who it's for | Example tasks |
|---|---|---|
| **Translation review** | Native speakers, non-coders | Review/fix the 10 machine-authored languages in `i18n.ts` |
| **Docs & onboarding** | Writers, first-timers | README screenshots, localized onboarding, doc fixes |
| **Good first issues** | New coders | Small UI fixes, copy, validation, test additions |
| **Bill parsers / extraction** | Intermediate | Regional bill-format coverage (`services/parsers/`, vision prompts) |
| **Core / services** | Experienced | Q&A, embeddings, dashboard, API endpoints |
| **Infra / quality** | DevOps-minded | CI jobs, runner setup, analytics, low-bandwidth pass |

Each on-ramp maps to labels (below) so contributors can self-select.

---

## 3. Contributor onboarding path

The goal: **from "interested" to "merged first PR" in under a week.**

1. **Land** — `README.md` → `CONTRIBUTING.md` (fork/clone, setup, the one rule).
2. **Run it locally** — backend + mobile setup already documented in `README.md`;
   the core flow degrades gracefully without API keys, so no secrets are needed to
   start.
3. **Pick a good first issue** — labeled, scoped, with acceptance criteria.
4. **Hooks + checks** — `pre-commit install`; CI runs ruff/mypy/pytest on the PR.
5. **PR** — branch from `main`, conventional commit, link the spec/issue.
6. **Review** — maintainer reviews within an agreed SLA (see §6); first-PR
   reviews are mentoring-first, not gatekeeping.
7. **Recognition** — contributor credited in release notes / contributors list.

**What we will add to smooth this (tracked as tasks):**
- A curated set of **`good first issue`** and **`help wanted`** issues.
- **Issue templates** (bug / feature / docs) — currently missing (no
  `.gitlab/issue_templates/`); adding them is an onboarding multiplier.
- A short **`docs/DEVELOPMENT.md`** quick-start consolidating setup + architecture.

---

## 4. Week-by-week plan (12-week cycle)

> Mirrors the user-growth cycle so the two run in lockstep.

### Phase A — Make the repo contributable (Weeks 1–3)
| Week | Action | Success signal |
|---|---|---|
| 1 | Add issue templates, a `CONTRIBUTING` quick-start link, and labels (`good first issue`, `help wanted`, `translation`, `parser`). | A newcomer can find a scoped task in 2 minutes. |
| 2 | Seed **8–12 good first issues** across on-ramps; write acceptance criteria. | Backlog of starter tasks exists. |
| 3 | Publish a translation-review guide for `i18n.ts`; tag one language as a pilot. | First translation PR opened. |

### Phase B — First contributor cohort (Weeks 4–7)
| Week | Action | Success signal |
|---|---|---|
| 4 | Run a **contribution session / workshop** with the home community (Swecha / campus club). | ≥3 first-time contributors. |
| 5 | Pair new contributors with a mentor; review PRs fast. | First external PRs merged. |
| 6 | Open translation review for 2–3 more languages via native-speaker volunteers. | Indic UI corrections merged. |
| 7 | Convert top user feature-requests (from `growth-strategy.md`) into labeled issues. | Contributors pick up user-driven work. |

### Phase C — Scale across institutions (Weeks 8–12)
| Week | Action | Success signal |
|---|---|---|
| 8 | Reach out to **2–3 new colleges / FOSS clubs**; offer a starter-issue list. | New institutions engaged. |
| 9 | Stand up a recurring community touchpoint (chat channel + monthly call). | Active contributor conversations. |
| 10 | Launch a light **mentorship track**: each new region/college gets a point-of-contact maintainer. | Each active institution has a mentor. |
| 11 | Recognize contributors publicly (release notes, shout-outs). | Retention of repeat contributors. |
| 12 | **Cycle review** — what brought contributors, what stalled; refresh this doc. | Next-cycle plan documented. |

---

## 5. Horizontal expansion (across institutions & regions)

Contributor expansion is horizontal the same way user expansion is — by **place,
language, and institution**:

| Vector | How we expand | Tie-in |
|---|---|---|
| **Institutions** | One college/club at a time, each with a maintainer point-of-contact and a starter-issue list | Mirrors `geographical-expansion.md` tiers |
| **Languages** | Each new region brings native speakers who own their language's translation review | `i18n.ts` review gate |
| **Regional bill formats** | Local contributors supply real bills + parser improvements for their region | Feeds extraction quality |
| **Swecha ecosystem** | Use existing FOSS-community events and channels as a distribution network | Lowest-cost, highest-trust |

Principle: **don't recruit contributors faster than you can mentor and review
them.** Each new institution opens only when a maintainer can support it.

---

## 6. How we keep contributors (retention)

| Lever | Practice |
|---|---|
| **Fast feedback** | CI gives automated results in minutes; target first human review within a few days |
| **Mentoring-first reviews** | First PRs are coached, not just judged |
| **Clear scope** | Issues carry acceptance criteria; the "one rule" removes ambiguity |
| **Recognition** | Credit in `CHANGELOG.md` / release notes and a contributors list |
| **Path to grow** | On-ramps let a contributor move from docs → translations → parsers → core |
| **Respect for time** | Small, well-scoped issues; no churned-out busywork |

---

## 7. Metrics we steer by

| Metric | What it tells us |
|---|---|
| New contributors / cycle (by on-ramp) | Which entry points work |
| Time-to-first-merged-PR | Onboarding friction |
| Repeat-contributor rate | Are we retaining people |
| Open `good first issue` count | Is the on-ramp stocked |
| Translation languages reviewed | Indic UI trustworthiness (10 still machine-authored) |
| Active institutions / regions | Horizontal reach |
| PR review turnaround | Maintainer responsiveness |

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Stale/empty issue backlog turns newcomers away | Keep ≥8 good first issues stocked; refresh each cycle |
| Slow reviews kill momentum | Review SLA; more maintainers as the community grows |
| Translation contributions hard to verify | Native-speaker review gate; corrections are single-file PRs |
| Recruiting faster than mentoring capacity | Gate new institutions on maintainer availability |
| Knowledge bottleneck on one maintainer | Document architecture; grow a co-maintainer bench |

---

## 9. Review cadence

- **Weekly:** triage new issues/PRs; keep the good-first-issue backlog stocked.
- **End of each 12-week cycle:** review contributor metrics, refresh this document.
- **Owners:** maintainer(s) in `CONTRIBUTING.md`; a point-of-contact per active
  institution/region.

_Related: [`growth-strategy.md`](growth-strategy.md) (user growth & continuous
improvement), [`geographical-expansion.md`](geographical-expansion.md) (regional
reach & onboarding)._
