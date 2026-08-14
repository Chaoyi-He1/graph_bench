# Experiments

Running record of the experiments backing the paper. Every number here is
reproducible from the scripts named beside it; per-case outputs live under
`runs/` (git-ignored) and the aggregates are committed.

## E-contamination — is the corpus recall-solvable?

`scripts/contamination_probe.py` · all 229 released cases

Each case's **opening report alone** is handed to a model with no chance
to ask anything, and it must state the root cause and the landed fix. A
grader with the answer key decides hit / partial / miss.

| | count | share |
|---|---|---|
| hit (names mechanism AND fix class) | 5 | **2.2%** |
| partial (one of the two) | 8 | 3.5% |
| miss | 216 | 94.3% |

By issue year — the discriminating check, since pretraining exposure
should favour older threads:

| year | n | hit | partial |
|---|---|---|---|
| 2021 | 3 | 0 | 0 |
| 2022 | 5 | 0 | 0 |
| 2023 | 98 | 3 | 6 |
| 2024 | 66 | 1 | 2 |
| 2025 | 48 | 1 | 0 |
| 2026 | 9 | 0 | 0 |

No age gradient. The five hits are listed in
`runs/contamination_summary.json` and can be excluded as a
decontaminated subset; at 2.2% they do not move aggregate scores.

Reading: the benchmark measures interactive diagnosis, not recall. This
is a check CAB does not report.

## E-review — what the two-stage review protocol is worth

Stage 1 (reviewer files findings against the full thread) refuses ~95% of
cases. Stage 2 (independent verifier re-checks each finding against the
thread, marking CONFIRMED or UNSUBSTANTIATED) leaves 89–95% of cases with
no confirmed high-severity defect.

That gap is the finding: a single-pass reviewer is not usable as a
release gate — it rejects almost everything, mostly on claims its own
evidence does not support. Verification is what makes model review
actionable.

Corollary from the rescue round: of 29 cases blocked in the first round,
**25 passed after being redrafted** under the hardened rules. Their
defects came from the generation prompt, not from the source threads.

## E-variance — the noise floor any comparison must clear

> **Superseded — re-measurement pending.** Both rounds below predate two
> corrections. (i) The agent's per-turn output budget was left unset, so
> the gateway capped output at 1000 tokens and a reasoning model spent it
> all on reasoning; the affected rows returned empty replies, which score
> as bad turns. `scripts/run_validity.py` now fails any row above a 5%
> empty rate, and the current baseline passes at 0.0%. (ii) The simulator
> fidelity fixes (see E-simfix) changed how turns are matched and how
> stalls terminate. The **qualitative** conclusions below still hold —
> aggregate grade is stable across identical runs while binary rates are
> not — but every number must be re-measured before it is quoted.

Two **identical** rounds (same model, same prompts, same corpus, same
judge) over a random 50-case paired subset of the frozen release, run
from a git worktree pinned to the release tag so corpus edits cannot leak
in. 49 cases completed in both rounds.

| metric | round A | round B | drift |
|---|---|---|---|
| mean grade | 0.5437 | 0.5363 | **−0.007** |
| resolved | 10 (20.4%) | 6 (12.2%) | **−8.2 pts** |
| reached terminal | 20 (40.8%) | 16 (32.7%) | **−8.1 pts** |

Per-case instability between the two identical runs:

| | |
|---|---|
| cases whose `resolved` verdict flips | 8/49 (**16.3%**) |
| cases whose `terminal` verdict flips | 8/49 (16.3%) |
| per-case abs grade delta | mean 0.117, median 0.100, p90 0.250, max 0.429 |
| cases with abs grade delta ≤ 0.05 | 12/49 (**24%**) |

Two things follow, and they pull in opposite directions:

1. **The aggregate grade is stable.** Mean grade moved 0.007 between
   identical runs — under 1.5% relative. A cross-model difference of a few
   hundredths on this metric is meaningful at n≈50.
2. **Binary outcome rates and per-case scores are not.** `resolved` and
   `terminal` each moved ~8 points, and one case in six flips outright;
   three quarters of cases move more than 0.05 in grade. A single run
   cannot support a per-case claim, and a resolved-rate gap smaller than
   roughly 8 points at this sample size is inside the noise.

Practical rules adopted for the paper: report mean grade as the headline
comparison metric; report resolved/terminal rates only with ≥2 rounds per
configuration and state the observed drift band alongside them; never
draw a conclusion about an individual case from one run.

This is also why the benchmark's own difficulty profile is quoted from
the larger round (n=164) rather than from the variance subset.

## E-simfix — what the simulator was measuring that the agent did not do

`scripts/check_simulator_acts.py` guards every fix below · four paired
arms over the same 50-case subset, same agent (gpt-5.6, `max_tokens`
8000), same judge; 49 cases completed and judged in all four.

The investigation started from a single number: **44% of cases in every
row triggered a forced reveal, and the rate barely moved across models
(43–45%)** — a signal that belonged to the harness, not to the agents.
Decomposing the 284 fires in the baseline row by what filled the stall
counter before each one:

| driver | share of fires |
|---|---|
| partial deadlock — same edge partially matched 2–3× in a row | 26–38% |
| routed to the solution side at a node with no solution edge | 25–36% |
| question outside the graph's clarification set | 21–43% |
| the agent genuinely failing a modeled path | **7–11%** |

Four defects behind that, each fixed and measured:

1. **Binary act routing.** A turn was classified as *either* a question
   *or* a proposal. Routed to "proposal" at a node whose out-edges are all
   clarifications, it could not match anything by construction — 35–44% of
   all no-matches. This penalised a turn *format*: among such turns, the
   share that also contained a question was 87% for Kimi-2.5 and 71% for
   GLM-5.1 against 9% for gpt-5.6, so the models that bundle hypothesis,
   step and question in one reply were charged for it.
2. **Fabricated negative results.** A proposal that matched nothing was
   answered "I tried that; nothing changed" even where the case models no
   fix attempt from that state at all. The simulator was inventing
   evidence, and it argued agents off correct paths.
3. **Content-blind partial follow-ups.** A partial got a canned "give me
   the exact steps" even when the steps were already given and what was
   missing was the account of the fault. The agent repeated itself into
   the insurance.
4. **Canonical paths that refused blind edges.** Most real threads reach
   their fix *through* a failed attempt, so an early node's only route to
   the terminal often crosses one blind edge into its aftermath state.
   Excluding those edges left **34% of non-terminal nodes and 55% of start
   nodes with no canonical path**; the insurance then had nothing to
   reveal and terminated the case as a dead end. This is what killed
   **48–54% of every run at a median of turn 5**, out of a 20-turn budget,
   and those cases carried the lowest grades in every row.

| metric | baseline | fixes 1–3 | + fix 4 | + fix 5 |
|---|---|---|---|---|
| mean grade | 0.5694 | 0.5512 | **0.6367** | 0.6026 |
| paired delta vs baseline | — | −0.018 (24↑/24↓) | **+0.067 (35↑/14↓)** | +0.033 (25↑/23↓) |
| exact matches | 138 | 184 | 278 | 265 |
| partial matches | 90 | **60** | 81 | 80 |
| forced reveals | 58 | **35** | 126 | 122 |
| bucket-A turns | 98 | 60 | 87 | 67 |
| ↳ fabricated results | 79 | 40 | 58 | 42 |
| `failed_dead_end` | 25 (51%) | 24 (49%) | **0** | **0** |
| `terminal_resolved` | 7 (14%) | 11 (22%) | 8 (16%) | 11 (22%) |
| ran out of turns | 10 (20%) | 8 (16%) | 25 (51%) | 29 (59%) |
| median turns/case | 8 | 7 | 20 | 20 |

Readings:

- **Fixes 1–3 corrected the mechanism without moving the score.** Exact
  matches +33%, partials −33%, forced reveals −40%, fabricated results
  −49% — but the paired grade delta (−0.018, 24 up / 24 down) is inside
  the noise floor. That is the expected shape: they remove ways the
  harness charged an agent for something it did not do, and gpt-5.6 is the
  model least exposed to them. The models that should gain are the ones
  with the high bundled-turn rates, which this arm does not measure.
- **Fix 4 is the one that mattered**: +0.067 mean grade, 35 cases better
  against 14 worse, and every premature death removed.
- **Fix 5 did not pay.** Resetting the stall counter on a productive turn
  is the more intuitive semantics, but forced reveals moved 126 → 122 and
  the grade came out below the same configuration without it. Once a case
  can use its whole budget, most later turns surface no new information,
  so there is little left to reset. Shipped as
  `SimulatorConfig.reset_stall_on_progress`, default off.

Two consequences for how results are reported:

- **`forced_reveal` and `reached_terminal` are saturated** once cases live
  their full budget: 90% of cases now hit at least one forced reveal.
  Neither is usable as an agent metric; both are reported as harness
  health.
- **The 20-turn cap is now the binding constraint** — 51% of cases end by
  exhausting it, and **17 of those 26 were one hop from the terminal**.
  Raising the cap would convert most of them, at proportional cost.

Everything measured before this section — main table, difficulty profile,
noise floor — predates these fixes and must be re-measured.
