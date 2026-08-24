# Draft skeleton — claims with their evidence attached

Every section states the claim to argue, the numbers that carry it, and
where they come from. Numbers are quoted from `docs/results.md`, which is
regenerated from the run directories; if one disagrees, the run
directories win and `results_pack.py` should be re-run.

Sections marked **[pending]** name the experiment that would complete
them and the sentence it would support, so a gap is visible where the
prose will go rather than discovered at submission.

---

## 1. Introduction

**Claim.** An agent that debugs *with a person* must elicit evidence
before it can fix anything, and no existing benchmark grades that
conversation against a case-specific answer key.

**Open with the result, not the motivation.** Across four current models
and 229 real support threads, every model asks competently —
proactiveness lands in a 0.05 band, 0.916 to 0.968 — and they separate on
everything after that: hallucination 0.65/0.64 against 0.97/0.98,
explanation 0.80/0.68 against 0.48/0.43, recovery 0.69/0.62 against
0.38/0.32. **Asking is solved. Accounting for the fault is not.** That
split is invisible to a benchmark that scores a patch, and invisible to
one that scores a single turn.

**Why not execution.** Containerised reproduction excludes exactly the
problems users actually bring — drivers, devices, OS integration, account
state. CAB's own limitations section documents that selection bias
(`docs/related-work.md`).

**Why not a scripted user.** A simulator conditioned on the resolved
thread tells the agent things it has not earned. Measured: three leaked
turns under a transcript-conditioned profile against zero under this one
(`E-leakprofile`).

## 2. Related work

`docs/related-work.md` §1–§4 has the neighbour-by-neighbour argument and
§5 the defence checklist. **[todo]** cut to venue length; foreground the
three axes this work occupies (execution-free, answer-key-graded,
multi-turn-with-elicitation).

## 3. Task formulation

**Claim.** A resolved support thread can be annotated as a causal graph
whose nodes are (system state, information state) pairs, and that single
structure then does three jobs: it constrains the simulated user, it
grounds the judge, and it defines the metrics.

Definitions: `docs/method.md`. Metrics: `docs/metrics.md` — solution
call, L1/L2/L3 obtainability, the tier ladder, the five grade components.

**Worked example** (§3, figure): `gh_expo_expo_33911`. Six states, one
known-blind path with its aftermath twin, one shortcut edge, L1 and L3
clarifications, and a satisfaction condition that explicitly forbids
presenting the blind attempt as a complete fix. The recorded dialogue
runs six turns to an earned terminal, and each agent turn's match against
the graph is in the transcript. One case exhibits the entire DSL.

**The canonical-path rule is worth a paragraph.** Most real threads reach
their fix *through* a failed attempt, so an early state's only route to
the terminal often crosses a blind edge into its aftermath. A search that
refuses blind edges leaves 34% of non-terminal states and 55% of start
states unroutable (`E-simfix`, defect 4).

## 4. Corpus

**Claim.** 229 cases across 75 projects, no project above 4%, drafted by
model and passed by a two-stage review whose second stage is what makes
it a gate at all.

- Composition and sizes: `docs/dataset-stats.md`, `docs/corpus-v2.md`
- Review protocol and what it caught: `E-review` — single-pass refuses
  ~95%, verification leaves 89–95% releasable, and 25 of 29 blocked cases
  passed after redrafting, so the defects came from the prompt rather
  than the threads
- Not recall-solvable: `E-contamination` — 2.2% hit from the opening
  report alone, no age gradient. This doubles as the single-turn ablation
- Provenance and licensing: `DATA_LICENSE.md`,
  `docs/data-collection-and-privacy.md`

**[todo] Threats to validity.** The corpus is machine-drafted and
machine-reviewed. State it plainly; the audit trail is the mitigation,
and `data/REVIEW_FINDINGS.json` is published.

## 5. Evaluation protocol

**Claim.** The simulator says only what its graph position licenses, and
this is checked rather than asserted.

- Ten offline invariants, no network: `scripts/check_simulator_acts.py`
- Compliance audit: `E-leak` — 9 flags in 10,715 user turns, every one
  read and explained, zero unexplained reveals
- Validity gate: `scripts/run_validity.py`. Motivate it with the actual
  incident — an unset output budget made one row 76% empty replies and it
  scored as incapability
- Ruling procedure: paired t plus sign test (`docs/metrics.md`), and why
  it replaced a multiple-of-drift rule that ignored sample size

## 6. Results

**Main table** (`docs/results.md`): four models, 229 cases, 30 turns.

| model | grade | resolved | forced walk | ran out |
|---|---|---|---|---|
| gpt-5.6 | 0.5991 | 29% | 48% | 20% |
| gpt-5.5 | 0.5634 | 31% | 45% | 21% |
| GLM-5.1 | 0.3877 | 26% | 50% | 21% |
| Kimi-2.5 | 0.3824 | 23% | 45% | 31% |

Rulings: the two tiers are 0.21 apart (t = 20.4 / 19.4). Within the GPT
tier 0.036 is small but real at n=229 (t = 3.4, p = 0.001). Between
GLM-5.1 and Kimi-2.5 there is nothing to call (t = 0.6).

**Headroom.** Fewer than a third of cases end with the user confirming a
fix the agent earned; roughly half reach a terminal only because the
insurance walked them there; a fifth to a third exhaust 30 turns.

**Robustness.**
- Different simulator model: delta −0.0007 (`E-simswap`). The scores are
  not an artefact of who plays the user
- Turn budget 20 vs 30: grade unchanged, truncated cases 56% → 21%
  (`E-turnbudget`)
- **[pending]** `E-judgeswap` — does the ranking survive a judge from
  another family? Supports: "the ranking is a property of the agents, not
  of the judge."

**Ablations.**
- Single-turn: `E-contamination`, 2.2%
- Judge with and without the graph term: `E-judge-ablation` — the plain
  rubric average separates these runs slightly *more*. Report it as it
  came out; the annotation layer earns its place by constraining the
  simulator and defining the answer key, not by the grade arithmetic
- **[pending]** `E-images` — the reporter's screenshots, against a
  multimodal agent. The first attempt measured nothing because the
  reference agent never read images
- **[pending]** `E-counterfactual` — sensitivity against specificity when
  the user's answer changes. Supports: "the agent conditions on what the
  user said rather than pattern-matching the report"

## 7. Analysis

**Elicitation and diagnosis come apart.** The rubric table is the
evidence; Kimi-2.5 reaches terminals slightly *more* often than gpt-5.6
and matches nearly as many edges, and still scores 0.22 lower
(`E-fairness`).

**A benchmark measures its own defects until someone looks.** Before the
harness audit, forced-reveal rates were 43–45% across every model —
near-identical, because they were a property of the corpus and matcher.
Only 7–11% of those were an agent genuinely failing a modelled path
(`E-simfix`). Worth a subsection: an execution-free benchmark has no
crash to keep it honest, so the harness needs its own instrumentation.

**[todo]** Per-domain and per-difficulty breakdown.

## 8. Limitations

- Machine-drafted, machine-reviewed corpus; audit trail published
- The simulated user is an LLM conditioned on a graph position. `E-leak`
  bounds leakage lexically and cannot bound paraphrase
- The judge is an LLM. `E-judgeswap` tests cross-family agreement;
  **[pending]** agreement with a human is built (`judge_agreement.py`,
  and a browser tool) but unlabelled. State this plainly — it is the
  weakest link in an execution-free design and should not be buried
- `forced_reveal` and `reached_terminal` saturate; reported as harness
  health, not agent metrics
- Per-case scores are unstable (0.10–0.12 mean absolute drift between
  identical runs); no claim rests on one case
- English-only, open-source projects only
- 229 cases: small-and-deep, with τ-bench (165) and ITBench-AA (59) as
  precedent

## 9. Release

Apache-2.0 code, CC BY 4.0 curation layer, pseudonymised threads,
per-case review pages, `scripts/export_hf.py` for the dataset release.
**[todo]** benchmark name; anonymised artifact mirror.

---

## What would change if the pending experiments come out badly

Worth deciding now rather than after seeing them.

- **`E-judgeswap` disagrees on ordering** — then the ranking is
  judge-specific and §6 says so; the tier split at t = 20 is unlikely to
  invert, but the within-GPT 0.036 would not survive
- **`E-counterfactual` shows low sensitivity** — that is a finding about
  the agents, not a failure of the experiment: it would mean they
  pattern-match the opening report. Report it
- **`E-images` shows screenshots matter** — then the text-only main table
  understates every model and needs saying; the ranking is unaffected
  since all four rows are text-only
- **The id-rendering arm moves scores** — then the main table was
  produced under a defect and must be re-run before submission. This is
  the only pending result that can invalidate the headline table
