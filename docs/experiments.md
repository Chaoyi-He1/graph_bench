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
