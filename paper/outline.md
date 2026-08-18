# Paper outline — evidence map

Working title: *Causal-graph-grounded, execution-free evaluation of
conversational debugging agents from real support threads.*

Status key: **[have]** evidence exists in-repo · **[partial]** started,
incomplete · **[running]** in flight · **[todo]** not started. Every claim
in the paper must trace to a file listed here.

## 1. Introduction

Claim chain: agents that debug *with a person* must elicit evidence, not
just patch code; existing benchmarks either require live execution
(costly, environment-biased) or script the user; nobody grades the
diagnostic conversation itself against a case-specific answer key.

- **[have]** Niche argument, neighbor-by-neighbor: `docs/related-work.md`
- **[have]** Headroom: under the corrected harness the strongest model
  earns an unforced terminal state in 13% of cases and exhausts its turn
  budget in 21% (`docs/experiments.md` E-turnbudget)

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
- **[have]** Answer-key-not-transcript principle and the canonical walk,
  including the two-tier canonical search: most real threads reach their
  fix *through* a failed attempt (`docs/method.md` §4)
- **[todo]** Formal figure: one worked case from graph to dialogue

## 4. Corpus construction

- **[have]** Three harvesters + filter gates + drafting + machine gates:
  `docs/pipeline.md`, `src/graph_bench/pipeline/`
- **[have]** Corpus v2.1 — **229 released cases across 75 projects**,
  ≤4% per project: `docs/corpus-v2.md`, `docs/dataset-stats.md`
  (regenerated from the released set only, `scripts/corpus_stats.py`)
- **[have]** The release is exactly `metadata.hitl_reviewed: true`; the
  55 review-blocked drafts ship alongside with their findings
- **[have]** Two-stage review and what it is worth: `docs/experiments.md`
  E-review — single-pass refuses ~95%, verification leaves 89–95%
  releasable; 25 of 29 blocked cases passed after redrafting, so the
  defects came from the prompt, not the threads
- **[have]** Generation-method convergence: `docs/convergence-report.md`
- **[have]** Privacy/licensing: `docs/data-collection-and-privacy.md`
- **[todo]** Threats-to-validity paragraph: the corpus is machine-drafted
  and machine-signed; state it plainly with the audit trail as mitigation

## 5. Evaluation protocol

- **[have]** Leak-safe simulator (node-scoped conditioning, allow-list
  render context), edge matching, tiering, judge rubrics:
  `src/graph_bench/user_simulator/`, `src/graph_bench/judge/`
- **[have]** Metric definitions: `src/graph_bench/recorder/metrics.py`
- **[have]** Ten offline invariants, no network:
  `scripts/check_simulator_acts.py`
- **[have]** Row validity gate — an unset output budget made one row 76%
  empty replies and it scored as incapability: `scripts/run_validity.py`
- **[todo]** Metric table with formal definitions + worked example

## 6. Experiments

| Exp | What it shows | Status |
|---|---|---|
| E-simfix | what the harness was charging agents for that they did not do | **[have]** four paired arms; only 7–11% of forced reveals were genuine agent failure |
| E-leak | the simulator never said more than the agent earned | **[have]** 9 flags in 10,715 turns, all adjudicated, zero unexplained reveals |
| E-contamination | the corpus is not recall-solvable (this is also the single-turn ablation) | **[have]** 2.2% hit, 3.5% partial, no age gradient |
| E-review | model review needs a verification stage to be a release gate | **[have]** |
| E-variance | the noise floor any comparison must clear | **[have]** corrected: ±0.021 mean grade, 15% of resolved verdicts flip |
| E-turnbudget | 30 turns buys conclusions, not score | **[have]** exhaustion 56% → 21% for 10% more turns |
| E-fairness | Kimi's deficit is diagnosis, not elicitation | **[have]** reaches terminals more often; hallucination 0.857 vs 0.252 |
| E2 oracle separability | scripted profiles split on grounding, not luck | **[have]** conservative grounded 1.00 · cheater 45 fishing turns → 0 leaks |
| E5 main table | model × metrics on the frozen corpus | **[running]** four models × 229 cases × 30 turns |
| E1 leakage A/B/C | what the anti-leak invariant is worth, measured with `leak_audit.py` against a transcript-conditioned simulator | **[running]** profile A arm |
| E7 ablations | no-images · structured vs plain judge · L-level gating | **[partial]** no-images queued (`send_images`); single-turn covered by E-contamination; other two need implementing |
| E4 judge–human agreement | the judge is the measuring instrument | **[partial]** `scripts/judge_agreement.py` builds a stratified, unanchored sheet; needs human labels |
| E3 counterfactual sensitivity | answers change when evidence changes | **[todo]** 608 authored variants ready |
| E8 simulator swap | results survive a different simulator model | **[todo]** one config flag |

## 7. Analysis

- **[have]** Elicitation and diagnosis separate: a model can run the
  conversation competently — matching as many edges, reaching terminals
  more often — and still fail the case on what it asserts (E-fairness)
- **[have]** Harness artifacts masquerade as capability: before the
  fixes, forced-reveal rates were near-identical across models (43–45%)
  because they were a property of the corpus and matcher
- **[todo]** Per-domain and per-difficulty breakdowns once the main table
  lands

## 8. Limitations

- Machine-drafted, machine-signed corpus (audit trail published)
- Simulator fidelity: the user is an LLM conditioned on the current node.
  E-leak bounds the leakage lexically; it cannot bound paraphrase
- Judge is an LLM; the agreement study is built but unlabelled
- `forced_reveal` and `reached_terminal` saturate once cases live their
  full budget (90% of cases hit at least one reveal) — reported as
  harness health, not as agent metrics
- Per-case scores are not stable (identical rounds move a case by 0.15 on
  average); no claim rests on a single case
- English-only threads; open-source projects only
- 229 cases: small-and-deep (τ-bench 165, ITBench-AA 59, SWE-bench
  Verified 500 as precedent)

## 9. Release

- **[have]** Apache-2.0 code, permissive-source data, private identity
  maps, per-case review pages
- **[have]** `docs/datasheet.md` (v2.1)
- **[todo]** HF dataset card + loader, anonymized artifact mirror,
  benchmark name

## Immediate critical path

1. Main table (E5) — running; four rows × 229 cases at 30 turns.
2. E1 leakage comparison — profile A arm running; `leak_audit.py` then
   turns the compliance self-check into a claim against the
   transcript-conditioned baseline every CAB-style simulator uses.
3. Human agreement study (E4) — the only item that needs a person; the
   sheet is generated and withholds the judge's scores so the annotator
   is not anchored.
4. E3, E7's remaining two ablations, E8 — each a config flag or a small
   judge variant, all cheap next to E5.
