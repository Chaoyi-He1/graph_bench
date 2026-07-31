# Data-Preparation Pipeline (CAB correspondence)

The pipeline mirrors CodeAssistBench's staging (arXiv:2507.10646) and replaces
its container-synthesis stage — the source of CAB's self-admitted selection
bias toward containerizable repositories — with graph drafting + machine
validation, which is what makes environment-bound threads usable.

| Stage | CAB | graph_bench |
|---|---|---|
| Repo collection | stars/date/permissive-license filters + community score | curated repo list of environment-bound, permissive-license projects (Flutter, Expo, Home Assistant core, ...) |
| Issue coarse filter | regex: ≥2 participants, no media-only | search API: closed, resolved label where available, `comments>12`, created window; profiling pass: reporter participation ≥3, bot exclusion, attachment count |
| Issue-level LLM filter | 7 yes/no questions (resolved, specific, clear, safe) | 7 yes/no gates incl. `environment_bound` and `annotatable` (`pipeline/prompts.py::FILTER_PROMPT`) |
| Message-level filter | drop "+1"/"thanks" | handled inside drafting (the graph keeps only diagnostic content by construction) |
| Environment synthesis | 2-stage LLM Dockerfile generation + fault-directed repair (≤3) | **graph drafting** with schema few-shot + validation repair loop (≤2), then semantic lint (terminal reachability, clarification presence, image references) |
| Answer standard | satisfaction conditions | satisfaction conditions **plus** the graph itself (edge-level answer key, blind paths, info levels) |
| User references | BM25 style anchoring on original replies | authored `user_answer_in_this_oncall` per clarification + persona hint; original attachments delivered as evidence |
| Verification | Docker build/run where available | execution-free: schema validators + expansion dry-run + human review queue (`hitl_reviewed`) |

## Run

```
export GRAPH_BENCH_LLM_BASE_URL=...   # OpenAI-compatible Responses endpoint
export GRAPH_BENCH_LLM_API_KEY=...
export GRAPH_BENCH_LLM_MODEL=...
uv run scripts/prepare_github_cases.py --target 10
uv run scripts/validate.py 'data/github_v0/graphs/*.json'
uv run scripts/scrub.py --apply        # before any public push
```

Stages are resumable (existing raw threads and graphs are reused). The
report lands at `data/github_v0/report.json` with per-thread profiling
stats, filter verdicts, and draft outcomes.

## Notes

- Attachments are archived at crawl time: GitHub attachment URLs redirect to
  signed S3 links that expire within minutes.
- Drafts are marked `hitl_reviewed: false`; they enter the benchmark proper
  only after human review (the pilot's defect checklist applies).
- The drafting few-shot is the hand-annotated `bmo_1822845` pilot case, so
  prompt and schema cannot drift apart silently.
