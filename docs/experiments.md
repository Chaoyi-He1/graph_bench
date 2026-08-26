# Experiments

Running record of the experiments backing the paper. Every number here is
reproducible from the scripts named beside it; per-case outputs live under
`runs/` (git-ignored) and the aggregates are committed.

## What each experiment asks

| | question | verdict |
|---|---|---|
| E-contamination | can a model answer from the report alone, without asking? | no — 2.2% |
| E-review | is single-pass model review usable as a release gate? | no; verification is what makes it usable |
| E-variance | how far do identical runs drift, and how should claims be ruled? | 0.009-0.026; rule by a paired test, not by multiples |
| E-simfix | was the harness charging agents for its own defects? | yes — only 7-11% of forced reveals were real failure |
| E-leak | did the simulator ever say more than the agent earned? | no — 9 flags in 10,715 turns, all explained |
| E-subset | is the 50-case subset representative of the corpus? | yes (p = 0.30) |
| E-turnbudget | 20 turns or 30? | 30 — same grade, far fewer truncated cases |
| E-main | how do four models compare over all 229 cases? | two tiers, 0.21 apart |
| E-fairness | where exactly does the weaker tier lose? | not in asking; in explaining, recovering, and asserting |
| E-leakprofile | what is the anti-leak invariant worth? | leaks observed under the alternative; grade effect not established |
| E-simswap | does the result survive a different simulator? | yes, delta -0.0007 |
| E-judgeswap | does the ranking survive a different judge? | queued |
| E-judge-ablation | does grounding the judge in the graph buy discrimination? | no — the graph earns its place elsewhere |
| E-images | do the reporter's screenshots matter? | not measured; the agent never read them |
| E-counterfactual | does the agent's answer move when the evidence moves? | not measured; the sample was drawn wrong |

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

## E-variance — how far identical runs drift, and why that stopped being the ruling

`scripts/recheck_claims.py` re-derives this and re-tests every claim
that rested on it.

Three arms are identical from the agent's side: the reference, one that
passed a simulator flag as an agent key (the adapter ignores unknown
keys), and one that switched off images a non-multimodal agent never
read. Their pairwise drifts in mean grade:

| pair | n | drift |
|---|---|---|
| reference vs vision | 48 | 0.0091 |
| vision vs no-images | 50 | 0.0184 |
| reference vs no-images | 48 | 0.0260 |

**Three measurements of one quantity, a factor of three apart.** Per-case
absolute drift is 0.10–0.12 throughout, and roughly one `resolved`
verdict in seven flips between identical runs.

Two corrections follow, and the second matters more than the first.

**The earlier figure was wrong.** It was 0.021, measured on two arms
judged before the judge's truncation defect was found; the random 0.0
scores that defect produced inflated the apparent drift. Re-judged, the
same pair drifts 0.0091.

**And the ruling should never have been a multiple of it.** Every
"reportable / not reportable" call in this file was `delta / floor >= 2`.
That heuristic ignores sample size, which is exactly the information
needed: a 0.036 difference over 229 cases is real (paired t = 3.4, sign
test p = 0.001) while a 0.037 difference over 48 is not (t = 1.8,
p = 0.19). Ruling by multiples got both of those backwards.

Rulings now come from a paired test — t > 2.6 **and** sign-test p < 0.01,
both required, since t is sensitive to a few large swings and the sign
test only to direction. The drift table above is reported as context, not
as a denominator.

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

## E-leak — did the simulator ever say more than the agent earned

`scripts/leak_audit.py` · 10,715 user turns across the four baseline rows,
plus a static pass over all 229 released graphs

The benchmark's central claim is that the simulated user speaks only from
its graph position. That claim was asserted by construction — the speaker
sees a fixed allow-list of fields — but never audited against what the
runs actually said. This checks it.

**Method.** For each case, the answer-key vocabulary (distinctive words of
the terminal solution's required elements and of the satisfaction
conditions) is subtracted by everything the user has legitimately earned:
their own opening report, the visible symptoms of any state they have
reached, the authored answer to every clarification actually asked, and —
from a recorded reveal onward — everything. A turn is flagged when it uses
at least two remaining answer-key terms, one of which appears in at most
three cases' answer keys corpus-wide (pairs of ordinary words like
"configuration, source" were most of the first pass's false alarms).

| row | user turns | flagged | rate |
|---|---|---|---|
| gpt-5.6 | 2607 | 4 | 0.15% |
| gpt-5.5 | 2618 | 1 | 0.04% |
| GLM-5.1 | 2797 | 1 | 0.04% |
| Kimi-2.5 | 2693 | 3 | 0.11% |

All nine were read individually. None is a leak: seven are coincidental
overlap on ordinary words carried by the simulator's own fixed
follow-ups ("the behavior is unchanged… CPU usage rises"), one is a
legitimate measurement answer, and one is a case where the agent matched
a shortcut edge to the terminal on its first turn and was told that
state's outcome — earned, and recorded as such. **Zero unexplained
reveals in 10,715 turns.**

**Static pass.** A run only exercises the states it reaches, so the same
screen runs over the corpus itself, looking for a non-terminal state —
reachable without proposing anything — whose authored symptoms already
speak from after the resolution. Three fields match, all of the form
"with the patched build, X no longer happens". Each is entered by a
*measurement-class clarification* ("build the linked branch, run it
against the same scenario, and paste the result"), which the DSL admits
as a clarification because the user performs it and reports what they
see. The state is therefore earned by asking for that measurement, and
what remains to be diagnosed — why the change works — is still the
terminal edge's job. Recorded here rather than repaired, since repairing
would mean re-typing an edge the source thread supports.

A note on what this can and cannot show: the screen is lexical, so it
finds vocabulary that appears where it should not, not paraphrase. It is
a floor on compliance, not a proof of it — but it is a floor no
transcript-conditioned simulator can clear by construction, which is the
comparison that matters.

## E-turnbudget — 20 turns against 30

50-case paired subset, gpt-5.6, frozen configuration.

The grade barely moves; the outcome distribution changes completely.

| | 20 turns | 30 turns |
|---|---|---|
| mean grade | 0.6360 | 0.6504 (+0.014, t = 0.6 — not reportable) |
| ran out of turns | 27 (56%) | **10 (21%)** |
| `terminal_resolved` | 6 | 12 |
| `forced_walk_to_terminal` | 15 | 24 |
| median turns/case | 20 | 22 |

Median turns rise 10% because only the cases that were being truncated
use the extra room. Adopted at 30: a case that ends by exhausting its
budget reports nothing about the agent, and more than half of them were
doing that. The grade is not the reason — it does not move.

(The noise floor once quoted here has moved to E-variance, which owns it
and has since corrected it.)
## E-fairness — the gap is everywhere, and deepest on staying inside the evidence

All 229 cases per model, judged under the corrected rubrics:

| rubric (higher is better) | gpt-5.6 | gpt-5.5 | GLM-5.1 | Kimi-2.5 |
|---|---|---|---|---|
| asks for evidence before proposing | 0.687 | 0.569 | 0.366 | 0.331 |
| stays inside the evidence (1 − hallucination) | 0.644 | 0.705 | 0.088 | 0.052 |
| accounts for the fault | 0.855 | 0.825 | 0.565 | 0.510 |
| recovers from a failed step | 0.749 | 0.568 | 0.371 | 0.313 |

**Retracted: "asking is solved."** This section previously reported
proactiveness at 0.92–0.97 for every model and concluded that elicitation
was saturated while diagnosis separated them. That was a property of the
rubric wording — *"judge whether the agent proactively gathered info"*,
which any agent that asks many questions satisfies — and not of the
conversations.

The harness had been contradicting it all along. It counts how often an
agent proposes a fix from a state whose graph offers no solution edge —
that is, before the evidence chain is complete:

| | premature proposals per case | old proactiveness | corrected |
|---|---|---|---|
| gpt-5.6 | 2.36 | 0.968 | 0.687 |
| gpt-5.5 | 2.22 | 0.960 | 0.569 |
| GLM-5.1 | 3.77 | 0.916 | 0.366 |
| Kimi-2.5 | 4.00 | 0.946 | 0.331 |

A 1.7× behavioural difference that the rubric was reporting as 0.02.
Under the corrected wording — did the agent have the evidence *before*
proposing — the rubric tracks that count at Spearman ρ = −0.80, and
`scripts/rubric_sanity.py` checks it on every run. **The rewrite was
adopted because it agrees with a measurement no judge produced, not
because it reads better.**

What replaces the retracted claim is plainer: **the two tiers separate on
all four rubrics and never cross.** The deepest gap is staying inside the
evidence — the GPT pair at 0.64–0.71, the other two at 0.05–0.09,
asserting what their conversations do not support in nearly every case.

The reading that survives, now better supported: a model can hold a
competent-looking diagnostic conversation and be wrong throughout it.
Nothing in the shape of a transcript reveals that. Only checking each
assertion against what the user actually said does — which is what this
benchmark's answer key exists to make possible.

## E-judge-ablation — what grounding the judge in the graph buys (preliminary)

`scripts/judge_ablation.py` · no new runs: every component of the grade is
stored in `grade_components`, so both judges are recoverable from any
judged run.

The structured grade averages five terms — four LLM rubrics read off the
transcript, plus `info_grounded_rate`, the one term the graph supplies
(the share of solution calls made with the required information in hand).
Drop that term and you have the **plain** judge: a transcript read by a
model with no answer key, which is what an execution-free benchmark looks
like without the annotation layer.

| run | n | structured | plain | ρ |
|---|---|---|---|---|
| gpt-5.6 | 48 | 0.6360 | 0.7611 | 0.918 |
| Kimi-2.5 | 48 | 0.3908 | 0.4573 | 0.875 |
| gpt-5.6, 30 turns | 50 | 0.6565 | 0.7865 | 0.887 |
| gpt-5.6, rerun | 50 | 0.6602 | 0.7870 | 0.869 |

| | spread across runs | in noise floors (0.021) |
|---|---|---|
| structured | 0.2694 | 12.8× |
| plain | 0.3297 | **15.7×** |

**The result cuts against the obvious claim, and is recorded as such.**
The plain judge separates these runs slightly *more* than the structured
one, and the two track each other at ρ ≈ 0.87–0.92. On this evidence the
graph-derived term is not what makes the headline number discriminative —
it slightly compresses the gap. What the annotation layer demonstrably
buys sits elsewhere: it constrains the simulator (E-leak), defines the
answer key the tiers and required elements are scored against, and
supplies the structural outcomes (`terminal_resolved`, forced reveals)
that a plain rubric average cannot express at all.

Preliminary, and weak evidence: four runs of which two share a
configuration. It is recomputed on the main table, where four genuinely
different models over 229 cases make the comparison worth something.

## E-leakprofile — what the anti-leak invariant is worth

`--sim-config '{"leak_profile": "A"}'` · 48 paired cases

Profile A hands the simulator the reconstructed resolved conversation
before it speaks — the way a transcript-conditioned simulator works, and
the design this benchmark argues against. Everything else is identical.

| | profile C (production) | profile A (transcript-conditioned) |
|---|---|---|
| mean grade | 0.6360 | 0.6730 (+0.037) |
| turns flagged by `leak_audit.py` | **0 / 913** | **3 / 916** |

> **Retracted:** this section previously reported the +0.037 as leakage
> inflation worth 1.75x the noise floor, and argued the invariant's value
> from it. Under a paired test it does not hold — t = 1.8, sign test
> p = 0.19 over 48 cases. The difference is not distinguishable from
> run-to-run drift at this sample size. Establishing a grade effect would
> need the full corpus or repeated rounds; neither has been run.

What survives is the direct observation, and it is the stronger evidence
anyway: the lexical screen catches three leaked turns under A and none
under C. That is leakage seen, not inferred from a score. The screen is a
floor rather than a measure — it finds vocabulary appearing where it
should not and cannot catch paraphrase — so three-versus-zero understates
whatever profile A actually leaks.

The honest statement of the invariant's worth is therefore: a
transcript-conditioned simulator demonstrably says things the agent has
not earned, and this design demonstrably does not. Whether that changes
the headline score by a measurable amount is **not established here**.

## E-images — a null result, and why it is not evidence

`--sim-config '{"send_images": false}'` · 48 paired cases

| | with images | without |
|---|---|---|
| mean grade | 0.6360 | 0.6358 (**−0.0002**, 24↑/24↓) |

Exactly zero — because the reference agent never received the images in
the first place. The backbone carries them on the turn as
`latest_user_images`, the corpus hooks 62 cases' screenshots to the exact
state or clarification they evidence, and the adapter built its message
list from text alone. Removing evidence nobody consumed changes nothing.

The adapter now has a multimodal path (`{"multimodal": true}`, images
inlined as base64 data URLs), **off by default** so it cannot land in the
middle of the main table and make rows incomparable. Until this ablation
is re-run against a multimodal agent, the honest statement is that it has
not been measured — not that images do not matter.

## E-subset — is the 50-case subset representative?

The simulator fixes, the turn budget, the noise floor, the leakage
inflation and the no-images ablation were all measured on the same
50-case paired subset. The main table is the first chance to ask whether
that subset resembles the corpus, within a single run — same model, same
configuration, so nothing confounds it.

Partway through the row it looked as though it did not. At n=30 the
subset showed 13% `terminal_resolved` against 30% for the rest, a
17-point gap at z ≈ 1.9, and it was recorded here as suggestive pending
the full row. It did not survive:

| | n | `terminal_resolved` | mean grade |
|---|---|---|---|
| inside the variance subset | 48 | 11 (22.9%) | 0.6645 |
| the rest of the corpus | 173 | 53 (30.6%) | 0.6744 |

7.7 points, z = 1.04, **p ≈ 0.30**, and the grades differ by 0.010 —
half the noise floor. The subset is not harder than the corpus; the early
gap was small-sample noise, which is exactly what a 15%-verdict-flip rate
produces at n=30.

Recorded rather than deleted, because the sequence is the point: the
caveat was raised on a number that looked significant, and retracted on
the number that settled it. The absolute levels quoted from the subset
stand as corpus-representative, and the main table agrees with them —
0.6722 over 229 cases against 0.6559 for the same configuration on the
subset, a gap inside the noise floor.

## E-judgeswap — does the ranking survive a different judge?

`scripts/judge_swap.py` · queued behind the main table

The table is scored by a gpt-5.6-family judge, and gpt-5.6 is one of the
models it ranks. Self-preference is the first objection a reader will
raise, and "we wrote a careful prompt" is not an answer to it.

Each recorded row is re-judged by a judge from a different family
(GLM-5.1) and the two verdicts compared on the same transcripts. This
needs no new conversations, so it costs judging alone.

What the comparison decides:

* **Levels move, ordering holds** — the table's comparisons stand, and
  only the absolute grades are judge-specific. That is the expected
  outcome and the one worth stating explicitly.
* **Ordering moves** — the ranking is a property of the judge, not of the
  models, and must be reported as such.

Reported as mean grade under each judge, per-case absolute delta, and
Kendall's tau over the case ranking. The swap writes into a sibling
directory so a check on the primary result can never overwrite it.

## E-main — the four-model table

`scripts/main_table.py` · all 229 released cases, 30 turns, frozen
simulator configuration, judged under the rubric definitions now written
in `docs/metrics.md`

| model | n | grade | resolved | forced walk | ran out | turns | reveals/case |
|---|---|---|---|---|---|---|---|
| gpt-5.6 | 229 | **0.6244** | 66 (29%) | 110 (48%) | 45 (20%) | 21 | 3.1 |
| gpt-5.5 | 229 | **0.5741** | 71 (31%) | 103 (45%) | 47 (21%) | 20 | 2.8 |
| GLM-5.1 | 229 | **0.3033** | 59 (26%) | 115 (50%) | 49 (21%) | 22 | 3.7 |
| Kimi-2.5 | 229 | **0.2794** | 52 (23%) | 103 (45%) | 70 (31%) | 21 | 4.0 |

Every row reconciled 229/229 by `run_integrity.py`, zero parse failures,
`failed_dead_end` zero throughout.

| comparison | delta | t | sign p | |
|---|---|---|---|---|
| gpt-5.6 vs Kimi-2.5 | +0.345 | 31.7 | <0.0001 | reportable |
| gpt-5.6 vs GLM-5.1 | +0.321 | 32.1 | <0.0001 | reportable |
| gpt-5.6 vs gpt-5.5 | +0.050 | 5.3 | <0.0001 | reportable |
| GLM-5.1 vs Kimi-2.5 | +0.024 | 2.4 | 0.0003 | not reportable |

Two tiers 0.32–0.35 apart; an in-tier difference of 0.050 that is small
but solid at n=229; and nothing to call between GLM-5.1 and Kimi-2.5,
where the sign test clears and t does not, and both are required.

**These replace the numbers this section carried before** (0.599 / 0.563
/ 0.388 / 0.382). Those came from rubric instructions that never stated
their construct; re-judged against the written definitions the tiers
separate *further*, not less. Only the re-judged figures should be
quoted, with the judge that produced them named alongside.

Outcome columns are unchanged by the re-judge, since they come from the
simulator rather than from any rubric: fewer than a third of cases end in
a fix the agent earned, roughly half arrive at a terminal only because
the insurance walked them there, and a fifth to a third exhaust 30 turns.

## E-simswap — does the result survive a different simulator?

`scripts/run_row3.sh` with `SIM_MODEL` pinned to a different family · 50
paired cases

The simulator drives both the simulated user and the turn-to-edge judge,
so a result that only holds under one simulator is a property of that
model rather than of the benchmark.

| | reference simulator | swapped simulator |
|---|---|---|
| mean grade | 0.6360 | 0.6353 |

Paired delta **-0.0007**, t = -0.0, sign test p = 1.00 over 48 cases —
indistinguishable, and by a wider margin than any other comparison in
this file. The benchmark's scores are not an artefact of which model
plays the user.

## E-counterfactual — does the answer move when the evidence moves?

`scripts/counterfactual.py` · 1,635 authored alternative answers over all
229 cases, each marked with whether the right fix changes as a result

> **First run void, by a sampling error.** 58 interventions executed
> cleanly and only **5** could be scored: an intervention is readable
> only against a case where the agent proposed a fix *of its own*, and in
> the 20-turn baseline used for sampling, most cases reached their
> terminal through a forced reveal. Where the proposal on record is the
> simulator's, changing the user's answer cannot move something the agent
> never chose. The planner did not filter on this and 55 of 60 came back
> uncomparable.

The fix is one constraint at sampling time, now in `plan --baseline`:
draw only from cases where the baseline produced a self-earned solution
call. Against the main-table row that is **146 of 229 cases**, all of
which carry counterfactual candidates — so the experiment is
comfortably feasible, it was simply drawn from the wrong pool.

Re-drawn: 60 interventions over 53 cases, balanced 30/30 between variants
that should change the fix and variants that should not. Queued.

What it will report: **sensitivity** (the proposal moved when it should
have) against **specificity** (it held when it should not). An agent that
pattern-matches the opening report scores high on one and low on the
other; only an agent actually conditioning on what the user said can score
well on both.

## E-idfix — the main table survives a simulator defect

`--sim-config` unchanged; the simulator itself differs · 48 paired cases

`describe_symptoms` concatenated volunteered information as raw
identifiers, so 6.4% of user turns across the main table — 1,248 of them,
in 198 of 229 cases — contained a bare token like
`build_containing_oid_handling_fix_resolves_error`. The main table was
produced under that defect. Whether it mattered was measured rather than
argued.

| | raw identifiers | rendered as words |
|---|---|---|
| mean grade | 0.5580 | 0.5603 |

Difference +0.0022, paired t = 0.09, sign test p = 0.67, 26 cases up
against 22 down. **Not distinguishable from re-running the same
configuration.** The four main-table rows stand as published; no re-run.

Two readings, and the second is the one worth keeping:

- The fix was still right to make. A reporter does not speak in
  identifiers, and one of those ids states its case's answer outright —
  the realism argument does not depend on a score moving.
- **A defect visible in 86% of cases changed nothing measurable.** That is
  a caution about inferring impact from prevalence: the tempting
  inference — it appears everywhere, so it must matter — was available,
  cheap, and wrong. It cost one 50-case arm to find out, against four
  days to re-run the table on a guess.

## E-judgeswap — a scale inversion, not a judge disagreement

`scripts/judge_swap.py` · rows one and two, re-judged by GLM-5.1

Re-judging with a different family first appeared to destroy the headline
result: gpt-5.6 over Kimi-2.5 was +0.2167 (t = 20.4) under the primary
judge and +0.0090 (t = 0.7) under GLM-5.1. The two checks that would
explain that away both failed — the alternative judge's grades spread as
widely as the primary's (sd 0.120 and 0.165 against 0.144 and 0.135), and
the divergence was not a uniform offset but concentrated almost entirely
in one rubric cell: Kimi's hallucination, 0.979 against 0.494.

Reading the two judges' rationales for the same case settled it. On
`gh_trinodb_trino_24572` the primary wrote that the agent *"asserted a
definitive leak, cited unverified issue numbers and even a placeholder
commit"* and scored **1.0**. GLM-5.1 wrote that the agent *"repeatedly
hallucinated specific GitHub issue numbers, commit hashes and version
numbers to support its incorrect diagnosis"* and scored **0.0**.

**The judges agree about what happened and disagree about which end of
the scale means it.** Across 229 cases their hallucination scores
correlate at **−0.16**.

The cause was in the prompt, which never stated a direction:

```
Judge whether the agent claimed unsupported facts.
Return JSON with keys score (0-1), rationale, evidence_turn_indices
```

Nothing there says whether 1 means "hallucinated heavily" or "did well".
The primary read it as a quantity of hallucination, GLM as a quality
score. Both readings are defensible, which is the defect.

Every rubric instruction now states its direction and both anchors —
including the three whose direction had only ever been implicit, and
therefore only ever lucky. **The numbers above are void and so is the
conclusion drawn from them**; the swap is re-running against the fixed
prompts, and whether the ranking survives is once again an open question
rather than a settled one.

Worth recording that this is the **third** time the same trap has been
sprung here: the annotation sheet told a human "1 = nothing invented"
while the judge meant the reverse; the agreement scorer averaged the
rubrics raw; and now the judge's own prompt. A scale whose direction is
not written down will eventually be read both ways.
