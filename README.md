# TraceGraph-Bench (working title)

Causal-graph-grounded, **execution-free** evaluation of conversational debugging agents, built from **real public support threads**. This repository is the paper workspace: method notes, related-work survey, pilot data, schema + validators, and the collection/privacy plan.

> Status: pilot complete (4 annotated Mozilla Bugzilla cases, all passing machine validation). Not yet public — see release gates below.

## Why

Multi-turn debugging benchmarks either require executable environments — excluding exactly the environment-bound problems real users bring (drivers, devices, OS integrations, account state; CAB's own limitations section documents this selection bias) — or condition simulated users on resolved transcripts, leaking future knowledge into the dialogue. We annotate resolved threads as causal graphs — nodes are (system-state, information-state) pairs; edges are clarifications (including user-executable measurements), solutions, and known blind paths — and use the **same graph** to (a) structurally constrain the user simulator, (b) ground an execution-free judge, and (c) derive causal metrics. See [docs/method.md](docs/method.md).

## Layout

```
docs/method.md                        method distillation (paper §3 source)
docs/related-work.md                  2026-07 survey with sources (paper §2/§6 source)
docs/pilot-study.md                   4-case pilot: funnel, findings, costs
docs/data-collection-and-privacy.md   wave plan, scrubbing, licensing, anti-contamination
paper/outline.md                      framing, contributions, experiment plan
src/tracegraph_bench/models.py        schema (pydantic) + semantic validators
scripts/validate.py                   validate graphs, check image refs
data/trial/graphs/*.json              4 annotated task graphs
data/trial/raw/*.json                 raw thread snapshots (Bugzilla REST; PRE-scrub)
data/trial/images/ + MANIFEST.json    archived attachments, sha256 + provenance
```

## Quickstart

```
uv run scripts/validate.py
```

validates every trial graph against the schema (edge-type consistency, reference integrity, information-state containment) and checks that all referenced attachments exist.

## Release gates (do not publish before)

1. **Scrubbing:** `data/trial/raw/` and graph texts are pre-pseudonymization snapshots (they contain reporter emails/usernames from the public Bugzilla). Run the full §5 scrub of [docs/data-collection-and-privacy.md](docs/data-collection-and-privacy.md) before any public push.
2. Online replay smoke on English content (pilot F7) — before any scale-up claim.
3. `artifacts` schema extension for non-image evidence (pilot P0).

## Licensing (intended)

Code: Apache-2.0. Curation layer (graphs/annotations): CC BY 4.0. Underlying thread content remains © its authors, sourced from the public Mozilla Bugzilla with per-case attribution links; redistribution follows the bugbug / BugsRepo precedents. See [DATA_LICENSE.md](DATA_LICENSE.md).
