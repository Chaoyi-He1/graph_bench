# Metrics — formal definitions

Every quantity the paper reports, defined against the code that computes
it. Section references are to `src/graph_bench/`.

## The unit of measurement: a solution call

A turn in which the agent proposes a fix is matched against the current
state's outgoing solution edges. A match produces a **solution call**
carrying the edge it matched, whether that edge was a *shortcut* (a
planted copy of a later fix, reachable before the evidence chain is
complete), and which of the edge's `required_info` the agent had actually
obtained at that point, split by obtainability level:

| level | meaning |
|---|---|
| **L1** | any user states it unprompted |
| **L2** | inferable from evidence already surfaced |
| **L3** | must be asked for, or measured |

## Tier of a solution call

`recorder/tiers.py`. Deterministic, in this precedence:

| tier | condition | step score |
|---|---|---|
| `forced_reveal` | the simulator supplied the step, not the agent | 0.0 |
| `needs_inference_check` | shortcut edge — the judge decides whether the skip was reasoned | 0.4 |
| `blind_guess` | L1 or L2 information still missing | 0.1 |
| `degrade_to_shortcut` | only L3 missing | 0.4 |
| `informed` | every required level satisfied | 1.0 |

A `needs_inference_check` the judge resolves becomes `inferred_shortcut`
(0.8) if the reply demonstrates reasoning over the skipped information,
`blind_shortcut` (0.4) otherwise. **The distinction is what an agent
displayed, not what it may privately have known** — private reasoning
telemetry is supplementary evidence, since most agents surface inference
only in the reply.

## Case outcomes

Exactly one per case, from the simulator's terminal state:

| outcome | meaning |
|---|---|
| `terminal_resolved` | reached a terminal state by the agent's own proposal, and the user confirms |
| `forced_walk_to_terminal` | reached the terminal only because the stall insurance walked it there |
| `premature_satisfaction` | the user believes it is fixed at a state the case marks as not resolved |
| `failed_dead_end` | the insurance found no canonical path — see the note below |
| `none` | the turn budget ran out |

`failed_dead_end` should be **zero** in any current run. Non-zero means
the canonical search failed to route a state, which was a harness defect,
not an agent outcome.

## Reported quantities

**grade** — the headline. Mean of five components, each in [0,1]:

```
grade = mean( info_grounded_rate,
              proactiveness,
              1 - hallucination,
              explanation,
              recovery )
```

Four are LLM rubrics read off the transcript. One, `info_grounded_rate`,
is supplied by the graph: of the solution calls the agent made *of its
own* (forced reveals excluded from the denominator), the fraction made
with every required piece of information in hand.

**Note the direction of `hallucination`**: it scores *how much* the agent
asserted that the conversation does not support. Zero is clean. The grade
uses its complement. Three of the four rubrics are "more is better" and
this one is not — a trap that has already produced one defect in this
repository's own tooling.

**resolved** — count of `terminal_resolved`. Not a rate over attempts;
one case contributes at most one.

**forced reveals per case** — how often the simulator had to supply a
step. Above ~3 per case this is a property of the corpus and the matcher
more than of the agent, and is reported as harness health.

**solution-step score** — weighted mean of the step scores above over a
case's resolved tiers. Reported alongside the grade, not folded into it,
so grades stay comparable across revisions of the tier weights.

## Ruling on a difference

Per-case grades are paired across arms, since every arm runs the same
cases. A difference is called real only when **|t| > 2.6 and a two-sided
sign test gives p < 0.01** — both required, because t is sensitive to a
few large swings and the sign test only to direction.

This replaced an earlier rule of "at least twice the run-to-run drift",
which ignored sample size and consequently got two rulings backwards in
opposite directions: a 0.036 difference over 229 cases is real, a 0.037
difference over 48 is not. Run-to-run drift is still reported (`docs/
results.md`), as context rather than as a denominator.

## What is deliberately not a metric

**`reached_terminal`** saturates once cases can use their full turn
budget — roughly half of all cases arrive at a terminal via the
insurance — so it measures the harness, not the agent.

**Per-case grade.** Identical runs move a single case by 0.10–0.12 on
average and flip roughly one `resolved` verdict in seven. No claim in the
paper rests on an individual case.
