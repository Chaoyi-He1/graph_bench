# Generation-Method Convergence Report

Date: 2026-08-02. Question: is the testcase-generation method (gateway
gpt-5.6 drafting + machine gates + Opus adversarial audit loop) good enough?
Verdict: **converged** — evidence below.

## Protocol

Each round: every task graph is read against its full source thread by an
Opus auditor under a 14-class defect catalog; every finding is then
independently refuted-or-confirmed by an Opus skeptic with the source in
hand. Only confirmed findings count. Confirmed findings drive (a) surgical
repairs to the corpus and (b) durable upgrades to the method — prompt rules,
few-shot examples, and machine gates — so each round improves future
generation, not just the audited files.

## Trajectory (22-case corpus; audits by identical Opus protocol)

| Round | Confirmed | High | Med | Low | Avg/case | needs_rework |
|---|---|---|---|---|---|---|
| R1 (initial drafts) | 71 | 7 | 28 | 36 | 3.23 | 17/22 |
| R2 (post leak-repair wave) | 38 | 4 | 13 | 21 | 1.73 | 11/22 |
| R3 (post verification/exit rules) | 32 | 2 | 9 | 21 | 1.45 | 6/22 |
| R4+R5 audit (25 cases incl. unseen) | 37→35 | 2 | 9→8 | 24 | 1.40 | 4-5/25 |
| R6+R7 repairs | all confirmed high/medium findings fixed; the final structural high (154241 canonical route) proven repaired against the runtime canonical-walk algorithm | 0 known | 0 known | ~noise | — | — |

Two of the late highs were introduced by our own mechanical repair scripts
(collapsed duplicate solution; inverted IS-NULL claim; identical-answer
string replace) — audit caught them, thread evidence fixed them.

## Systemic classes: eliminated or gated

Every class with ≥4 confirmed instances in R1 is now machine-gated at draft
time or reduced to ≤3 idiosyncratic instances:

| R1 class (count) | Now |
|---|---|
| future_knowledge_leak (18) | measurement-answers-are-raw-output rule + two leak-repaired few-shots; R5 unseen drafts: 0 |
| unfaithful_reveal (13) | first-person voice rule; residual instances individually repaired |
| symptom_contains_diagnosis (8) | observable-only rule incl. aftermath/terminal bars |
| required_but_ungettable (5) | **hard validator**: availability + orphan-info + required/inferred disjointness |
| logistics_gate (4) | denoise rule; R3 onward: ≤1 |
| image_misassignment (4) | uniqueness + provenance lint |
| verify-before-fix inversion (R3 emergent) | rule 4d + tail template + vocabulary lint; all instances reshaped |
| stranded nodes / blind-only exits (R3 emergent) | canonical-exit lint + rollback materialization + load-time rollback expansion |

## Generalization (the actual method test)

Three never-before-seen threads (duckdb ×2, home-assistant ×1) drafted by
the final pipeline and audited by the same protocol: **0 high, every verdict
minor_issues**, avg 1.33 confirmed (all but one low). Auditor's wording on
the duckdb case: "The graph is unusually faithful ... every timing, row
count and file size in the user answers matches the thread verbatim; the
measurement-class rule is applied correctly and deliberately."

## Audit noise floor

Cases with **no edits between rounds** still drift by ±1 low finding per
round (observed repeatedly: pytorch 0→1, curl_10936 0→1, nodejs 0→1→0, and
verifiers reversing each other on the through-failure-spine convention).
Residual per-case low findings sit at this instrument noise level, so
further whole-corpus repair rounds would chase auditor sampling variance,
not method defects. Per-case human sign-off (`data/REVIEW.md`) remains the
final gate for corpus membership, as designed.

## Machine gates now standing (all 25 graphs pass)

Schema validators: edge-type consistency; reference integrity; info-state
containment; required-info availability; orphan-info introduction;
required/inferred disjointness. Lint: terminal presence/reachability;
stranded-node and blind-only-start checks; verification-timing heuristic
(4d) with try-build exemption; required-vs-declared level consistency;
image existence/uniqueness/provenance. Loader: rollback + shortcut
expansion. Drafting: two leak-repaired few-shots; repair rounds carry the
full conversation; reporter comments uncapped at 4× the default.
