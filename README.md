# graph_bench (working title: TraceGraph-Bench)

Causal-graph-grounded, **execution-free** evaluation of conversational debugging agents, built from **real public support threads**. Paper workspace + benchmark harness + data pipeline.

> Status: corpus v2.1 — **229 released cases** across 75 projects, each machine-validated and passed by a two-stage model review ([docs/corpus-v2.md](docs/corpus-v2.md)). The repository also ships the 55 drafts that review blocked, with their findings; **the released set is exactly the graphs carrying `metadata.hitl_reviewed: true`**, and every published number describes that set alone. Harness, four-model matrix, contamination probe and simulator-fidelity experiments are in [docs/experiments.md](docs/experiments.md) — note that the pre-fix result tables there are marked superseded and are being re-measured.

## Why

Multi-turn debugging benchmarks either require executable environments — excluding exactly the environment-bound problems real users bring (drivers, devices, OS integrations, account state; CAB's own limitations section documents this selection bias) — or condition simulated users on resolved transcripts, leaking future knowledge into the dialogue. Here each resolved thread is annotated as a causal graph — nodes are (system-state, information-state) pairs; edges are clarifications (including user-executable measurements), solutions, and known blind paths — and the **same graph** (a) structurally constrains the user simulator, (b) grounds an execution-free judge, and (c) yields causal metrics. See [docs/method.md](docs/method.md).

## Layout

```
src/graph_bench/
  oncall_graph/      schema (pydantic + semantic validators), shortcut/rollback
                     closure, mermaid visualization
  user_simulator/    graph-position-constrained simulator (anti-leak), edge
                     matcher/judge prompts, persona speaker
  backbone/          agent-agnostic run loop (recovery ladder, resume,
                     bounded parallelism) + scripted & OpenAI-compatible agents
  recorder/          lossless per-turn JSONL + deterministic metric rollup
  judge/             terminal scorer (rubrics + tiers; stub backend for CI)
  pipeline/          GitHub harvest + CAB-style filter + LLM graph drafting
scripts/             validate.py · prepare_github_cases.py · scrub.py
                     corpus_stats.py (released-set statistics) ·
                     check_simulator_acts.py (offline simulator invariants) ·
                     run_validity.py (is a recorded row scoreable at all) ·
                     contamination_probe.py · variance_report.py · run_ab.sh
data/trial/          4 hand-annotated Mozilla pilot cases (+ raw, images)
data/github_v0/      LLM-drafted GitHub cases (raw, images, graphs, report)
docs/                method · related-work survey · pilot study · collection
                     & privacy plan · pipeline correspondence
paper/               outline (framing, contributions, experiment plan)
```

## Quickstart

Everything LLM-related reads an OpenAI-compatible **Responses API** endpoint
from env (`cp .env.example .env` and fill in; no credentials in the repo):

```
uv run scripts/validate.py                       # validate all task graphs
uv run python -m graph_bench backbone run \
    --agent scripted --tasks 'data/trial/graphs/*.json' \
    --run-id smoke --out /tmp/gb_runs            # offline end-to-end
uv run python -m graph_bench judge run /tmp/gb_runs/smoke   # stub judge
```

Online (simulated user + LLM edge-matching + an API-backed agent):

```
uv run python -m graph_bench backbone run \
    --agent api --tasks 'data/trial/graphs/bmo_1822845.json' \
    --run-id live1 --out data/runs --online --max-turns 8
uv run python -m graph_bench judge run data/runs/live1 --online
```

Prepare new cases from GitHub (see [docs/pipeline.md](docs/pipeline.md)):

```
uv run scripts/prepare_github_cases.py --target 10
```

## Release gates (do not publish datasets beyond this repo before)

1. **Scrubbing:** `scripts/scrub.py --apply` pseudonymizes identities in raw
   threads and graphs (identity map lands outside the repo). Screenshots
   still need the human checklist pass (docs/data-collection-and-privacy.md §5.3).
2. English online-replay quality check on the simulator/judge (pilot F7).
3. `artifacts` schema extension for non-image evidence (pilot P0).

## Licensing

Code: Apache-2.0. Curation layer (graphs/annotations): CC BY 4.0. Underlying thread content remains © its authors (public Mozilla Bugzilla and GitHub issue threads, per-case attribution links, takedown channel) — see [DATA_LICENSE.md](DATA_LICENSE.md).
