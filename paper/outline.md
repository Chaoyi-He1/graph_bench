# Paper outline — evidence map

Working title: *Causal-graph-grounded, execution-free evaluation of
conversational debugging agents from real support threads.*

Status key: **[have]** evidence exists in-repo · **[partial]** started,
incomplete · **[todo]** not started. Every claim in the paper must trace
to a file listed here.

## 1. Introduction

Claim chain: agents that debug *with a person* must elicit evidence, not
just patch code; existing benchmarks either require live execution
(costly, environment-biased) or script the user; nobody grades the
diagnostic conversation itself against a case-specific answer key.

- **[have]** Niche argument, neighbor-by-neighbor: `docs/related-work.md`
- **[have]** Headroom result to motivate: strongest available model
  resolves 1 in 5 of its own drafted cases (`docs/wp0-online-replay.md`)

## 2. Related work

- **[have]** `docs/related-work.md` §1–§4 (CAB, Dialogue SWE-bench,
  CirrusBench, JFTA, τ-family, ExCyTIn, clarification line,
  simulator-fidelity critiques, execution-free evidence base)
- **[have]** Defense checklist for the 2026 debate: same file §5
- **[todo]** Cut to venue length; foreground the three axes we occupy

## 3. Task formulation and DSL

- **[have]** Node = (system_state, info_state); clarification /
  solution / mixed edges; known-blind paths; shortcuts; L1/L2/L3
  obtainability; satisfaction conditions: `docs/method.md`,
  `src/graph_bench/oncall_graph/models.py`
- **[have]** Answer-key-not-transcript principle and the canonical walk
- **[todo]** Formal figure: one worked case from graph to dialogue

## 4. Corpus construction

- **[have]** Three harvesters + filter gates + drafting + machine gates:
  `docs/pipeline.md`, `src/graph_bench/pipeline/`
- **[have]** Statistics: `docs/dataset-stats.md` (79 cases, 7 domains,
  49 msgs/thread mean, 79% of clarifications are L3 must-ask)
- **[have]** Generation-method convergence: `docs/convergence-report.md`
  (confirmed defects 71 → cleared; generalization on unseen threads)
- **[have]** Sign-off procedure and what it caught: `docs/corpus-v1.md`,
  `data/REVIEW_FINDINGS.json`
- **[have]** Privacy/licensing: `docs/data-collection-and-privacy.md`
- **[todo]** Threats-to-validity paragraph: the corpus is machine-drafted
  and machine-signed; state it plainly with the audit trail as mitigation

## 5. Evaluation protocol

- **[have]** Leak-safe simulator (node-scoped conditioning, allow-list
  render context), edge matching, tiering, judge rubrics:
  `src/graph_bench/user_simulator/`, `src/graph_bench/judge/`
- **[have]** Metric definitions: `src/graph_bench/recorder/metrics.py`
- **[todo]** Metric table with formal definitions + worked example

## 6. Experiments

| Exp | What it shows | Status |
|---|---|---|
| E5 main table | model × metrics on the frozen corpus | **[partial]** one full round on the pre-freeze corpus (`docs/wp0-online-replay.md`); frozen-corpus runs paused by budget |
| E2 oracle separability | scripted profiles split on grounding, not luck | **[have]** conservative: grounded 1.00, informed 11/11, 9/12 resolved · cheater: grounded 0.17, informed 0, 11 forced reveals, 45 fishing turns → 0 leaks |
| E4 reliability | round-to-round variance, judge–human agreement, simulator swap | **[todo]** needs ≥2 frozen-corpus rounds; agreement study needs human labels |
| E1 leakage A/B/C | what the anti-leak invariant is worth | **[todo]** harness supports `--sim-config leak_profile`; runs not made |
| E3 counterfactual sensitivity | answers change when evidence changes | **[todo]** 608 authored counterfactual variants ready |
| E6 contamination | 0-turn probe, date buckets, canary | **[todo]** |
| E7 ablations | single- vs multi-turn, no-images, structured vs plain judge | **[todo]** |

## 7. Analysis

- **[have]** Failure-mode observation from the smoke round: high
  proactiveness (0.94) but weak conversion of gathered evidence into
  grounded solution calls (solution-step 0.46); 12/25 died circling in
  clarification
- **[todo]** Per-domain and per-difficulty breakdowns once the frozen
  main table exists

## 8. Limitations

- Machine-drafted, machine-signed corpus (audit trail published)
- Simulator fidelity: the user is an LLM conditioned on the current node
- Judge is an LLM; agreement study pending
- English-only threads; open-source projects only
- 79 cases: positioned as small-and-deep (τ-bench 165, ITBench-AA 59,
  SWE-bench Verified 500 as precedent)

## 9. Release

- **[have]** Apache-2.0 code, permissive-source data, private identity
  maps, per-case review pages
- **[todo]** HF dataset card + datasheet (`docs/datasheet.md` drafted),
  anonymized artifact mirror, benchmark name

## Immediate critical path

1. Frozen-corpus main table (E5) + a second round (E4 variance) — the
   only blocker is compute budget; harness and matrix rows are ready.
2. Human agreement study — needs a human labeler; sample and protocol
   can be prepared now.
3. E1/E3/E6 runs — each is a config flag away, all cheap relative to E5.
