# WP0 — First End-to-End Online Replay (2026-08-03)

First full run of the public harness on the public corpus: `backbone run
--agent api --online` over all 25 graphs, then `recorder metrics`, then
`judge run --online`. Agent, simulator and judge all ran against the same
GPT-5.6-class Responses endpoint (configured via `GRAPH_BENCH_LLM_*`; no
endpoint details are committed). This is the smoke baseline, not a paper
number: single round, agent = the drafting model playing its own corpus.

## Headline numbers (n=25)

| metric | value |
|---|---|
| mean judge grade | 0.559 (min .302 / median .552 / max .712) |
| user-confirmed resolved | 5/25 (20%) |
| reached a terminal node | 8/25 (32%) |
| stuck in clarification loop | 12/25 |
| mean turns to terminal (when reached) | 11.6 |
| rubric means | proactiveness .944 · explanation .692 · recovery .480 · non-hallucination .401 |
| solution-call tiers (resolved cases) | informed 2 · inferred_shortcut 4 · blind_shortcut 2 · forced_reveal 5 |
| solution_step_score / shortcut_groundedness | 0.462 / 0.667 |

Reading: a strong frontier model resolves only one case in five on its own
corpus — headroom is wide, and the failure mode is exactly the one the
benchmark targets (high proactiveness, weak conversion of gathered evidence
into grounded solution calls; 12 cases died circling in clarification).
Every leak-safety mechanism produced live samples on public data: forced
reveals, shortcut tier grading (inferred vs blind), stall escalation, and
dead-end termination.

## Harness fixes the smoke forced (shipped in 16e2e7b)

1. **English surface**: every generation-side literal (responder templates
   and reply intents, speaker fallbacks, rollback-edge text, oracle/probe/
   cheater scripts, leakage transcript builder) was still in the language of
   the internal ancestor; speaker prompts also carried a language bias. The
   first smoke run answered an English thread in Chinese. All generation
   surfaces are English now and speaker prompts mirror the conversation
   language; detection surfaces (matcher cues, judge inference check) stay
   bilingual on purpose.
2. **repo snapshots**: `metadata.repo_snapshot` (default-branch commit at
   issue-creation time) is now resolved at harvest for all three sources and
   backfilled for all 25 cases — the anchor for the repo-grounded track.
3. Neutral BM25 corpus default; `runs/` ignored.

## Known behaviors to carry into experiment design

- **Through-failure spines disable insurance at the start node.** Canonical
  precompute excludes blind and shortcut edges, so a graph whose N0 exits
  are {blind attempt, shortcut} has no canonical edge there: the stall
  insurance cannot force-walk, and a circling agent terminates as
  `failed_dead_end` (observed on curl_10936). Legitimate but must be
  remembered when interpreting forced-reveal counts per case shape.
- **Whole-graph clarification matching is by design**: information requests
  match authored clarifications anywhere in the graph (the user can run any
  measurement they will eventually run); node advancement stays bundle- and
  node-scoped. Solution matching is node-scoped.
- **Gateway 502 bursts** (upstream connect timeouts) killed 3/25 cases on
  the first pass. The retry ledger (`retries.json`, cap 2) plus resume
  semantics (finalized = present in `metrics.json`) recovered them: delete
  the partial `.jsonl`, rerun the same command — finished cases are skipped,
  ledger-eligible cases rerun, then re-run `recorder metrics` and
  `judge run` (already-judged cases are skipped without `--force`).
