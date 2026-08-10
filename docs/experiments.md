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

## E-variance (in progress)

Two identical rounds of the same model over the frozen released corpus,
to establish the noise floor any cross-model claim must clear. Runs from
a git worktree pinned to the release tag so corpus edits cannot leak in.
