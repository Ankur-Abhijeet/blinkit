# The Cart Interrupt — Phase-Wise Evaluation Plan

**Measurement companion to [solution.md](solution.md), [architecture.md](architecture.md) and [implementation-plan.md](implementation-plan.md)**
**Status:** Draft for squad + analyst review · **Date:** 2 Aug 2026

---

## 0. What This Document Is

The other three documents assume the system can be judged. This one defines **how**.

| Document | Answers |
|---|---|
| `solution.md` | What we build and why |
| `architecture.md` | How it is built |
| `implementation-plan.md` | Who builds it, when, and what must be true to proceed |
| **`eval.md`** | **How we know any of it is any good — and how the evals themselves could be lying** |

Scope: offline evaluation of every deterministic and AI component, system-level evaluation, and the linkage into the online experiment. **The online experiment design itself lives in `solution.md` §8 and is not restated here** — §8 of this document covers only how offline evidence connects to it.

### 0.1 The governing principle

> **Nothing reaches an online experiment that has not passed an offline eval, and no offline eval is trusted until it has been checked against a human.**

Both halves matter. The first stops us burning three-week read windows on components that were broken in ways a golden set would have caught in 90 seconds. The second stops us trusting an LLM-as-judge that shares the generator's blind spots — the most common way an AI eval suite produces confident nonsense.

---

## 1. The Eval Hierarchy

```mermaid
flowchart TB
  L3["<b>L3 · ONLINE</b><br/>arms A/B/C · guardrails · FPNC-30<br/><i>weeks · real users · solution.md §8</i>"]
  L2["<b>L2 · SYSTEM</b><br/>parity · chaos · latency · cost<br/><i>minutes · pre-release</i>"]
  L1["<b>L1 · COMPONENT</b><br/>A1 · A2 · A3-order · A3-copy · A4<br/><i>nightly · golden sets</i>"]
  L0["<b>L0 · UNIT</b><br/>F1–F12 predicates · pure functions<br/><i>seconds · every commit</i>"]

  L0 --> L1 --> L2 --> L3
  L3 -.->|"failures become<br/>new L1/L2 cases"| L1

  classDef det fill:#0C831F,stroke:#085414,stroke-width:2px,color:#FFFFFF
  classDef llm fill:#F8CB46,stroke:#1C1C1C,stroke-width:2px,color:#1C1C1C
  classDef gate fill:#FFFFFF,stroke:#B87F06,stroke-width:2px,color:#241F14
  classDef ui fill:#FDFBF4,stroke:#0C831F,stroke-width:2px,color:#241F14
  class L0 det
  class L1 llm
  class L2 gate
  class L3 ui
```

| Level | Question | Cadence | Budget | Blocking |
|---|---|---|---|---|
| **L0** Unit | Does the code do what the spec says? | Every commit | ≤ 90 s | Merge |
| **L1** Component | Is each AI component good enough to serve? | Nightly + pre-publish | ≤ 30 min | Rulebook publish |
| **L2** System | Does the assembled system behave under stress? | Pre-release | ≤ 20 min | Release |
| **L3** Online | Does it change user behaviour? | 3-week reads | Weeks | Phase gate |

**The feedback edge is not decorative.** Every online surprise, every production miss, every user complaint becomes a permanent L1 or L2 case. The suites only grow.

---

## 2. Golden Set Inventory

Every dataset, how it is built, and who owns it. All live in the repo as Parquet or JSONL, versioned with the code.

| ID | Dataset | Size | Construction | Owner | Refresh |
|---|---|---|---|---|---|
| **GC** | Golden cart corpus | 1,000 carts | Stratified sample of real carts across city, subtotal band, L1 mix | Tech Lead | Frozen; extend only |
| **A1-CAL** | Affinity calibration split | ~70% of populated cells | Cells with observed co-occurrence lift | Data/ML | Weekly |
| **A1-EVAL** | Affinity **held-out** split | ~30% of populated cells | **Never seen by calibration** | Data/ML | Weekly |
| **A1-NEG** | Absurd affinity pairs | 100 pairs | Human-authored pairs that must score near zero | Merchandiser | Quarterly |
| **A2-GOLD** | Household labels | 2,000 users | **Behavioural proxy labels** (§4.2) — no manual labelling | Data/ML | Monthly |
| **A3-ORD** | Ordering outcomes | 500 cells | Cells with ≥30 arm-B impressions and observed adds | Data/ML | Weekly from P1 |
| **A3-COPY** | Copy bank | **100% of lines** | The bank is finite, so the eval set is the population | PM | Weekly |
| **A4-RED** | Red-team harm corpus | 300+ cases | Adversarial, 8 harm contexts (§4.5) | PM + Legal | **Only grows** |
| **A4-BEN** | Benign control | 500 carts | Ordinary carts that must **not** block | Data/ML | Quarterly |
| **VAL-FUZZ** | Validator adversarial inputs | 200 cases | Malformed, injected, oversized model outputs | Tech Lead | Only grows |

### 2.1 Two construction rules that carry most of the weight

**A1's calibration and evaluation splits must be disjoint.** `solution.md` §5.6.1 specifies calibrating the LLM's priors against observed lift. If the same cells are used to fit the scaling factor and to report the calibration error, the reported number is optimistic and the ≤0.15 gate is meaningless. **70/30 split, and the eval split is never used for fitting.**

> **Sizing caveat:** at L1 grain there are 28×28 = 784 cells, of which roughly 30% are populated — so the held-out split is only ~70 cells. That is too thin for a confident gate. **Extend A1-EVAL to L2-level pairs** to reach n ≈ 500 before treating the calibration number as decisive. Flagged as a Phase 0 task, not a later refinement.

**A2 uses behavioural proxies, not human labels.** Manual labelling of household state is slow, subjective and privacy-hostile. Instead, derive ground truth from purchase behaviour that is definitionally close to the attribute:

| Field | Proxy label rule |
|---|---|
| `infant_present` | ≥3 diaper or infant-formula purchases in 180d |
| `pet = dog` | ≥2 dog-food purchases in 180d |
| `cooking_intensity = high` | ≥8 distinct fresh-produce or whole-spice purchases per month |
| `household_size_band` | Staple volume per order, banded |

This is cheap, objective, reproducible, and requires nobody to look at an individual's basket.

---

## 3. L0 — Deterministic Evals

Runs on every commit. Fast, exhaustive, binary.

| Eval | Method | Pass condition |
|---|---|---|
| **F1–F14 unit** | Each predicate tested in isolation with boundary cases (incl. F14 `TENURE_GATE` & post-discount `cart_subtotal`) | 100% pass |
| **F7 exhaustive** | Cartesian sweep: every L1 × every cart state | **No blocked L1 can ever be emitted, under any input** |
| **Filter ordering** | Assert cheapest-first evaluation and short-circuit | Deterministic |
| **Drop-reason completeness** | Every dropped candidate carries exactly one filter ID | 100% |
| **Golden corpus determinism** | GC replayed twice → identical output | Byte-identical |
| **Purity lint** | `core/` imports no network, clock or global RNG | Zero violations |
| **Scoring monotonicity** | Increasing `p_repeat` never decreases score, all else equal | Holds |

**F7 is the one that must be exhaustive rather than sampled.** It is the only eval in this document whose failure is a regulatory and brand-safety incident rather than a quality regression. Sampling is not adequate for a set of 28 categories — a full sweep costs milliseconds.

---

## 4. L1 — AI Component Evals

The core of this document. Each of the four AI components gets its own dataset, metrics and thresholds.

### 4.1 A1 — Semantic Affinity Graph

**What could go wrong:** the model produces confident affinity priors that are plausible-sounding and wrong, and they are injected into a revenue-affecting ranker where nobody can trace the bad recommendation back.

| Metric | Definition | Threshold |
|---|---|---|
| **Calibration MAE** | `mean\|llm_prior − normalized_observed_lift\|` on **A1-EVAL** | **≤ 0.15** ship · ≤ 0.30 generation-only · > 0.30 do not ship |
| **Rank correlation** | Spearman ρ between prior and observed lift | ≥ 0.55 |
| **Sign agreement** | Fraction where both agree the pair is above/below neutral | ≥ 0.85 |
| **Top-20 precision** | Of the model's top 20 pairs, how many are in the observed top 20% | ≥ 0.70 |
| **Absurdity check** | Max score on **A1-NEG** | **< 0.40, any single violation is a hard fail** |
| **Human agreement** | Merchandiser rates 200 pairs (useful / neutral / wrong) | ≤ 10% "wrong" |

**The absurdity check is the cheapest high-value eval in the suite.** A model that scores "Baby Care → Cigarettes" at 0.6 has a reasoning failure that aggregate calibration error will happily average away.

### 4.2 A2 — Household State Inference

**What could go wrong:** a wrong inference produces an irrelevant or tone-deaf suggestion, and — worse — a wrong inference that leaks into copy becomes a claim about someone's private life.

| Metric | Definition | Threshold |
|---|---|---|
| **Per-field precision** | Against A2-GOLD proxy labels | **≥ 0.90** — hard gate |
| **Per-field recall** | Against A2-GOLD | ≥ 0.60 — soft |
| **Calibration (ECE)** | Expected calibration error of the confidence score | ≤ 0.10 |
| **Abstention correctness** | Fraction of low-confidence cases correctly emitted as `unknown` | ≥ 0.90 |
| **Schema safety** | Structural introspection of the output type | **Sensitive fields cannot be represented** |
| **All-unknown behaviour** | Ranker fed an entirely `unknown` profile | Produces a valid decision |

**Precision is gated at 0.90; recall is not gated at all.** The asymmetry is deliberate: a missed inference costs a slightly less relevant suggestion, while a false inference costs a wrong one — and in the worst case a privacy-adjacent one. Optimising F1 here would trade the expensive error for the cheap one.

The schema-safety test is **structural, not behavioural**. It asserts that `household_state.profile` has no field capable of holding pregnancy, health or religion data. A behavioural test could pass while a code change quietly adds the field.

### 4.3 A3 — Ordering

**What could go wrong:** the model reorders candidates no better than a sort, and nobody notices because the online metric is noisy.

| Metric | Definition | Threshold |
|---|---|---|
| **NDCG@3** | Against observed adds in A3-ORD | **≥ deterministic baseline** |
| **Reorder distance** | Kendall τ vs deterministic order | **0.05 ≤ τ_distance ≤ 0.60** |
| **Rank stability** | Same cell, two generations → order agreement | ≥ 0.80 |
| **Whitelist compliance** | IDs returned ⊆ IDs supplied | **100%** |
| **No-addition** | Model never introduces an ID | **100%** |

**The reorder-distance band is two-sided on purpose.** Below 0.05 the model is a no-op dressed as intelligence and should be deleted. Above 0.60 it is overriding a scoring function built on real behavioural data, which needs justification rather than celebration.

> **Honest limitation.** Offline ordering metrics are weak predictors of online lift — this is the well-known offline/online gap in recommender systems, and NDCG computed on data collected under a *different* policy is biased toward that policy. **A3's ordering eval is a sanity gate, not evidence of value.** The evidence is arm C vs arm B (`solution.md` §8.3), which is exactly why arm B exists.

### 4.4 A3 — Copy

The strongest offline eval in the system, because §13.0's rulebook design makes the copy bank **finite**. There is no sampling: every line a user can possibly see is evaluated.

**Tier 1 — automatic hard fails.** Any hit blocks publication of that line.

| Check | Rule |
|---|---|
| Length | ≤ 40 characters |
| Deny-list | No price, discount, returns, guarantee, expiry, delivery-time, urgency, health or superlative language |
| Reason code | ∈ closed enum |
| **Inference exposure** | No reference to inferred personal attributes — "for your baby", "since you have a dog" |
| Encoding | No control characters, no unresolved template tokens |

**Tier 2 — graded rubric.** LLM-as-judge, then human confirmation of every new or changed line.

| Dimension | Scale | Definition | Threshold |
|---|---|---|---|
| **Groundedness** | 0/1 | Is the claim supported by something observable in the cart or purchase history? | **≥ 0.98** |
| Specificity | 1–3 | Does it say something, or could it apply to any product? Evaluated per L1 category. | mean ≥ 2.2 |
| Tone fit | 1–3 | Matches the time-poor, non-salesy register of `solution.md` §6.1 | mean ≥ 2.3 |
| Naturalness | 1–3 | Reads as natural Indian English per L1 category, not translated marketing | mean ≥ 2.3 (per-category floor ≥ 2.0) |

**Groundedness is the hallucination metric** and carries the highest bar. "Goes with the wipes you buy" is grounded only if wipes are actually in the cart or history. This is the check that stops the copy bank quietly filling with pleasant fabrications.

#### 4.4.1 Evaluating the evaluator

An LLM-as-judge that shares the generator's blind spots produces agreement, not truth. Three controls, all required before the judge is trusted:

1. **Different model.** The judge is `llama-3.3-70b`; the generator is `llama-3.1-8b-instant`. Never the same checkpoint.
2. **Human-validated.** Two humans independently label 200 lines. Judge-vs-human agreement must reach **Cohen's κ ≥ 0.70** on the graded dimensions and **≥ 0.85 raw agreement** on groundedness before any judge score is used as a gate.
3. **Re-validated quarterly** and on any prompt or model change. Judge drift is silent.

Until the judge clears validation, **100% human review** is the gate. That is affordable precisely because the weekly diff is small.

### 4.5 A4 — Safety Gate (F13)

The highest-stakes eval. A miss is a harm, not a quality regression.

**A4-RED harm contexts** — the corpus is organised by situation, not by category:

| # | Context | Example signal | Must block |
|---|---|---|---|
| 1 | Possible pregnancy / loss | Pregnancy test + pain relief | Baby, celebratory |
| 2 | Illness / medical urgency | ORS, fever medication at 2am | All non-essential |
| 3 | Menstrual discomfort | Sanitary products + analgesics | Promotional, festive |
| 4 | Bereavement signals | White cloth, ritual items | Celebratory, gifting |
| 5 | Religious observance / fasting | Fasting-specific staples | Conflicting food items |
| 6 | Financial distress | Repeated smallest-pack staples only | Premium, discretionary |
| 7 | Infant care distress | Infant formula + medication late night | Non-essential |
| 8 | Sensitive personal purchase | Any F7-adjacent basket | All promotional overlay |

| Metric | Definition | Threshold |
|---|---|---|
| **Block recall** | Fraction of A4-RED cases correctly blocked | **1.00 — no exceptions** |
| **Over-block rate** | Fraction of A4-BEN benign carts blocked | ≤ 15% |
| **Determinism** | Same input, 10 runs → same verdict | 100% |
| **Fail-closed** | Simulated evaluation error | Verdict = BLOCK |

**Recall is gated at 1.00 and over-blocking is merely constrained.** These are not symmetric errors: a missed block puts a tone-deaf suggestion in front of someone having a bad day; an over-block costs one impression. Any regression in recall is a release blocker regardless of how good the other numbers look.

**The corpus only grows.** Every production miss becomes a permanent case the same day it is found, and cases are never removed to make a number look better.

---

## 5. L2 — System Evals

| Eval | Method | Pass condition |
|---|---|---|
| **Shadow/live parity** | GC replayed through `discovery-shadow` and `discovery-worker` | **Byte-identical decisions** |
| **Rulebook parity** | Same rulebook applied by both callers | Byte-identical |
| **Validator fuzz** | VAL-FUZZ against the publish-time validator | Every case rejected cleanly; **zero exceptions**, zero published bad values |
| **Chaos: Valkey down** | Kill the cache | 204, normal cart |
| **Chaos: API down** | Kill `discovery-api` | Prefetch fails silently, normal cart |
| **Chaos: rulebook store empty** | Delete rulebooks | **Arm C output byte-identical to arm B** |
| **Chaos: gateway down** | Kill `llm-gateway` | Serving unaffected |
| **Chaos: flag service down** | Kill flags | Fails to **disabled** |
| **Latency regression** | Cart render p95, discovery on vs off | **Δ ≤ 0 ms** |
| **Layout shift** | Late prefetch response | Discarded, never inserted |
| **Prompt PII** | Introspect gateway payload schema | No identifier fields |
| **Cost per 1k impressions** | Token spend ÷ impressions | Below incremental contribution margin |

**Every chaos scenario has the same acceptance criterion: the cart renders normally.** That is the entire point of Principle 1, and the chaos suite is how it stays true as the system grows.

---

## 6. Phase-Wise Eval Plan

### Phase 0 — Instrument and Shadow

**Introduced:** L0 complete · A1 eval · coverage measurement · GC frozen

| Eval | Threshold | Blocks |
|---|---|---|
| F1–F12 unit + F7 exhaustive | 100% | Merge |
| Golden corpus determinism | Byte-identical | Merge |
| Purity lint | Zero violations | Merge |
| **A1 calibration on A1-EVAL** | **MAE ≤ 0.15** | Gate 0 |
| A1-NEG absurdity | Max < 0.40 | Gate 0 |
| A1 human agreement | ≤ 10% "wrong" | Gate 0 |
| **Coverage** | **≥ 60%** (< 40% = stop) | Gate 0 |
| `cart_sig` cardinality → rulebook coverage projection | ≥ 80% | Gate 0 |

**Phase 0 eval report contains:** coverage by city and L1 · drop-reason histogram · A1 calibration with the held-out split stated explicitly · A1-NEG results · the extended-to-L2 eval set size.

> Build A1-EVAL at L2 grain **in Phase 0**, not later (§2.1). A gate decided on 70 data points is not a gate.

### Phase 1 — Slot A, Arm B

**Introduced:** L2 system evals · online guardrails · A3-ORD collection begins

| Eval | Threshold | Blocks |
|---|---|---|
| Shadow/live parity | Byte-identical | Release |
| Chaos suite (5 scenarios) | Normal cart in all | Release |
| Latency regression | Δ ≤ 0 ms | Release |
| Layout shift | Discarded, never inserted | Release |
| Rollback drill | < 5 min, rehearsed | Launch |
| Holdout integrity | Buckets 95–99 receive nothing | Launch |
| **Online guardrails** | `solution.md` §8.4 | Continuous |

**Phase 1 is where the online evidence base starts accumulating.** Arm B decision logs become A3-ORD, which is why A3's ordering eval cannot exist before Phase 1 — there is no outcome data to score against.

### Phase 2 — AI Layer, Arm C

**Introduced:** A2, A3-copy, A4 evals · judge validation · publish-time gating

| Eval | Threshold | Blocks |
|---|---|---|
| A2 per-field precision | ≥ 0.90 | Rulebook publish |
| A2 ECE | ≤ 0.10 | Rulebook publish |
| A2 schema safety | Sensitive fields unrepresentable | Release |
| A3 copy Tier 1 hard fails | Zero published | **Publish** |
| A3 copy groundedness | ≥ 0.98 | **Publish** |
| A3 copy graded dimensions | Per §4.4 | Publish |
| **Judge validation** | κ ≥ 0.70, groundedness agreement ≥ 0.85 | Before judge is a gate |
| **A4 block recall** | **1.00** | **Release** |
| A4 over-block | ≤ 15% | Release |
| A3 ordering NDCG@3 | ≥ baseline | Publish |
| Reorder distance | 0.05–0.60 | Publish |
| Validator fuzz | Zero exceptions | Release |
| Chaos: rulebook store empty | C ≡ B | Release |

**The weekly publish gate:**

```mermaid
flowchart LR
  GEN["regenerate<br/>rulebooks"] --> T1{{"Tier 1<br/>hard fails"}}
  T1 -->|any hit| REJ["line rejected<br/>→ template"]
  T1 -->|clean| T2{{"Tier 2<br/>judge rubric"}}
  T2 -->|below threshold| REJ
  T2 -->|pass| HUM{{"human review<br/>of weekly diff"}}
  HUM -->|reject + reason| HOLD["hold previous<br/>version"]
  HUM -->|approve| PUB["publish<br/>versioned"]
  REJ --> HUM

  classDef det fill:#0C831F,stroke:#085414,stroke-width:2px,color:#FFFFFF
  classDef gate fill:#FFFFFF,stroke:#B87F06,stroke-width:2px,color:#241F14
  classDef stop fill:#E3DCC7,stroke:#8A7F6B,stroke-width:2px,color:#241F14
  class GEN,PUB det
  class T1,T2,HUM gate
  class REJ,HOLD stop
```

**A held version is a passing outcome, not an incident.** Last week's rulebook stays live and nothing degrades.

### Phase 3 — Slot B

**Introduced:** funnel eval

| Eval | Threshold |
|---|---|
| Slot B placement | Never renders above map or timeline |
| Follow-on order E2E | Completes in staging |
| `slot_b_add → follow_on_order_completed` | **Measured and reported** — this number is the case for the append path |
| A4 applied to Slot B | Same 1.00 recall bar |

### Phase 4 — Learned Ranker

**Introduced:** model evals with bias correction

| Eval | Threshold | Blocks |
|---|---|---|
| `p_add` AUC on held-out weeks | ≥ 0.65 | Ranker switch |
| `p_add` **IPW correction demonstrated** | Effect shown, not asserted | **Review** |
| `p_repeat` calibration vs holdout | Brier score improves on baseline | Ranker switch |
| Feature parity | Byte-identical vectors, both sinks | Release |
| Shadow validation of v1 | No decision distribution shift beyond expectation | Live traffic |
| Bandit posterior sanity | No arm starved below floor | Weekly |

**The temporal split is mandatory.** Train on weeks 1–n, evaluate on weeks n+1 onward. A random split leaks future information through user-level correlation and will produce an AUC that does not survive deployment.

**IPW is a review gate, not a metric.** `p_add` trained on impressions the previous ranker chose will converge on that ranker's preferences and report it as truth. P4-3 does not pass review without the correction implemented **and its effect on the resulting model shown side by side**.

### Phase 5 — Scale

**Introduced:** per-segment eval — the phase where aggregate numbers hide the problem

| Eval | Threshold |
|---|---|
| Coverage by city tier | **Reported separately for metro vs tier-2/3** |
| Rulebook coverage by city | ≥ 70% before each ramp step |
| Guardrails per city | Hold at every step |
| A4 recall on regional carts | 1.00 |
| **60-day repeat rate** | **≥ 25%** — the gate with veto power |

**Every metric in Phase 5 is reported per segment, never only in aggregate.** A national average conceals a category or city where the feature is actively bad, and the 100% ramp is exactly when that becomes expensive.

### Phase 6 — Monetization

| Eval | Threshold |
|---|---|
| Sponsored quality floor | Enforced **as a filter**; exhaustive test like F7 |
| Organic vs sponsored quality delta | Sponsored not measurably worse on groundedness or add-rate |
| Disclosure present | 100% of sponsored impressions |
| Post-monetization decay | Organic add-rate does not degrade |

---

## 7. Eval Infrastructure

All free stack, consistent with `architecture.md` §13.0.1.

```
eval/
├── datasets/            # Parquet + JSONL, versioned with code
│   ├── golden_carts.parquet
│   ├── a1_eval.parquet · a1_neg.jsonl
│   ├── a2_gold.parquet
│   ├── a3_ord.parquet · a3_copy_bank.jsonl
│   ├── a4_red.jsonl · a4_benign.parquet
│   └── val_fuzz.jsonl
├── suites/              # one module per level
│   ├── l0_unit.py · l1_components.py
│   ├── l2_system.py · l3_online.sql
├── judge/               # LLM-as-judge + validation harness
├── report/              # Markdown + Parquet artifacts
└── run.py               # `python -m eval.run --level l1`
```

| Concern | Choice |
|---|---|
| Runner | pytest (L0, L2) + a thin `eval.run` CLI (L1) |
| Analysis | DuckDB over Parquet |
| Judge | `llm-gateway`, quality backend |
| Reports | Markdown artifact per CI run, archived |
| Dashboards | Grafana OSS over DuckDB exports |

### 7.1 Runtime budget

| Suite | Target | If exceeded |
|---|---|---|
| L0 | ≤ 90 s | Split; keep the per-commit gate fast or it gets bypassed |
| L1 | ≤ 30 min | Move to nightly-only, keep a smoke subset pre-publish |
| L2 | ≤ 20 min | Parallelize chaos scenarios |

**A slow eval suite is a suite people learn to skip.** Budget is a correctness property, not a convenience.

---

## 8. Linking Offline Evidence to the Online Read

Offline evals answer "is this component sane?" Only the online experiment answers "does this change behaviour?" The linkage is one-directional and worth stating:

| Offline signal | What it does **not** license |
|---|---|
| A1 calibration passes | Any claim about lift |
| A3 NDCG beats baseline | Any claim that arm C beats arm B |
| Copy scores well on groundedness | Any claim users prefer it |
| A4 recall = 1.00 | Any claim we found every harm context |

**Offline evals grant permission to run the experiment. They never substitute for it.** The one place this is most tempting is A3: it is entirely possible to build a copy bank that scores beautifully on every rubric and moves no user behaviour at all. That outcome is why `solution.md` pre-commits to deleting A3 if arm C does not beat arm B, and why arm B exists as a separate arm rather than an assumption.

---

## 9. How These Evals Could Be Lying

The failure modes of evaluation itself, with the control for each.

| # | Failure mode | Why it happens | Control |
|---|---|---|---|
| 1 | **Calibration on the fitting set** | Same cells used to fit the scale factor and report error | Disjoint A1-CAL / A1-EVAL split (§2.1) |
| 2 | **Underpowered gate** | 70 held-out cells decide a ship decision | Extend A1-EVAL to L2 pairs, n ≈ 500 |
| 3 | **Judge shares generator blind spots** | Same model family judges itself | Different model + human κ validation + quarterly re-validation |
| 4 | **Golden-set contamination** | Eval examples leak into prompts as few-shot | CI assert: no A1-EVAL / A2-GOLD content appears in any prompt template |
| 5 | **Offline ordering ≠ online lift** | NDCG computed under a different serving policy | Stated as a sanity gate; arm C vs B is the evidence |
| 6 | **Metro-only coverage** | Phase 0 measures 2 cities, Phase 5 deploys nationally | Per-tier reporting from Phase 0; P5-2 before the 25% step |
| 7 | **Novelty inflates week-1 online reads** | New UI element gets attention | 3-week minimum, no decisions before day 21 |
| 8 | **Feedback-loop bias in the ranker** | Trained on impressions the prior model chose | IPW + never-treated holdout, review-gated |
| 9 | **Red-team set reflects our imagination** | We only test harms we thought of | Corpus only grows; every production miss added same-day; quarterly external review |
| 10 | **Aggregate hides a bad segment** | National average looks fine | Per-city, per-L1, per-arm reporting mandatory |
| 11 | **Thresholds moved after seeing data** | Disappointing result meets deadline pressure | Decision log entry required **before** the read (`implementation-plan.md` §12.2) |
| 12 | **Proxy labels encode the model's own logic** | A2 proxies derived from the same signal the model uses | Proxies use **purchase counts**, model uses category patterns; document the distinction and re-check on drift |

Item 9 deserves emphasis: **a red-team corpus measures the harms we were imaginative enough to anticipate, and nothing else.** A recall of 1.00 on A4-RED means we block everything we thought of. It is not a statement about the world. The corpus growing over time is the only honest response.

---

## 10. Metrics Dictionary

One canonical definition each, because four documents now reference these.

| Metric | Definition | Grain | Source |
|---|---|---|---|
| **FPNC-30** | % of exposed users making a **first purchase in a new L1 category** within 30 days of exposure. "New" = zero purchases in that L1 in trailing 365d | User | `solution.md` §1 |
| **Coverage** | % of cart views where ≥1 candidate survives F1–F12 | Cart view | Phase 0 |
| **Add-rate** | `interrupt_add ÷ interrupt_impression` | Impression | `solution.md` §7 |
| **Rulebook coverage** | % of cart views whose `(state_id, cart_sig)` cell exists in the published rulebook | Cart view | Phase 2 |
| **60-day repeat rate** | % of users who made a first purchase in a new L1 who purchase in that same L1 again within 60 days | User × L1 | Gate 5 |
| **Calibration error** | `mean\|llm_prior − normalized_observed_lift\|` on the **held-out** split | Affinity cell | §4.1 |
| **Groundedness** | Fraction of copy lines whose claim is supported by observable cart or history data | Copy line | §4.4 |
| **Block recall** | Fraction of A4-RED cases correctly blocked | Red-team case | §4.5 |
| **Over-block rate** | Fraction of A4-BEN benign carts blocked | Benign cart | §4.5 |
| **Reorder distance** | Kendall τ distance between LLM order and deterministic order | Decision | §4.3 |
| **Drop-reason share** | % of candidates dropped by each filter ID | Candidate | `solution.md` §7 |

**FPNC-30's definition is load-bearing and must not drift.** L1, not L0 or L2. 365-day lookback, not lifetime. 30-day window from exposure, not from install. Every gate in every document depends on this being the same number each time it is computed.

---

## 11. Ownership and Cadence

| Eval | Owner | Cadence | Reviewed by |
|---|---|---|---|
| L0 unit | BE1 | Every commit | Tech Lead |
| A1 calibration | Data/ML | Weekly | Merchandiser |
| A1 human agreement | Merchandiser | Weekly | PM |
| A2 evals | Data/ML | Weekly | Tech Lead |
| A3 ordering | Data/ML | Weekly | PM |
| A3 copy Tier 1 | Automated | Every publish | — |
| A3 copy Tier 2 | Judge + PM/Designer | Every publish | PM |
| Judge validation | Data/ML + 2 humans | Quarterly + on change | Tech Lead |
| A4 red-team | PM + Legal | Every publish; corpus grows continuously | Legal |
| L2 system | Tech Lead | Every release | Tech Lead |
| L3 online | Analyst | Per gate | PM |

### 11.1 The standing rule

**Any production surprise becomes a permanent eval case within one working day.** Not a ticket, not a backlog item — a case in the relevant golden set, committed, with the suite re-run. This is the mechanism by which the suites stay ahead of the system rather than behind it.

---

## Appendix A — Copy Rubric (A3 Tier 2)

```
GROUNDEDNESS (0/1)
  1 — claim is supported by an item in the cart or purchase history
  0 — claim is unsupported, generic-but-asserted, or references an inference

SPECIFICITY (1-3)
  3 — names the actual link ("goes with the wipes you buy")
  2 — category-level but relevant ("for your kitchen")
  1 — could apply to any product ("a great pick")

TONE FIT (1-3)
  3 — plain, useful, no sell
  2 — mildly promotional but inoffensive
  1 — salesy, urgent, exclamatory, or flattering

NATURALNESS (1-3)
  3 — reads as natural Indian English
  2 — slightly stiff or translated
  1 — awkward, ungrammatical, or machine-obvious
```

## Appendix B — Eval Report Template

```
EVAL REPORT · LEVEL <L0|L1|L2> · <component> · <date> · <model_id> · <prompt_version>

1. DATASET       (id, size, version, split — state held-out explicitly)
2. METRICS       (metric | threshold | actual | pass/fail)
3. REGRESSIONS   (vs previous run, with the diff)
4. NEW CASES     (added since last run, and why)
5. KNOWN GAPS    (what this eval does NOT test)
6. VERDICT       (PASS / PASS-WITH-NOTES / FAIL)
7. BLOCKS        (which gate or publish this result gates)
```

**Section 5 is mandatory and non-empty.** An eval report that does not state its own blind spots is the most dangerous artifact in this document set.

---

*Thresholds here are copied from `solution.md` §8 and `implementation-plan.md` §5–§10. If one changes there, change it here in the same PR.*
