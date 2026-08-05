# Corpus v1.0 — 79 signed cases

Frozen 2026-08-05. Every case in `data/*/graphs/` carries
`metadata.hitl_reviewed: true`, meaning it passed a release sign-off
review. Evaluation runs intended for publication should be executed
against this frozen state (`git tag corpus-v1.0`).

## Composition

| Domain | Cases | Sources |
|---|---|---|
| Mozilla non-UI | 15 | bugzilla.mozilla.org Core (networking, JS engine, workers, IndexedDB) |
| systems / networking | 13 | moby, curl, traefik, containerd, etcd |
| databases | 12 | postgresql-bugs, duckdb, ClickHouse |
| ML / inference | 12 | vllm, ollama, llama.cpp, pytorch |
| web frameworks | 10 | flutter, expo |
| language runtimes | 9 | deno, nodejs, cpython |
| IoT / home automation | 8 | micropython, home-assistant |

Three harvesters (GitHub REST, Bugzilla REST, postgresql.org list
archives) feed one drafting pipeline; each case carries
`metadata.repo_snapshot` — the default-branch commit of the (mirror)
repository at issue-creation time — for the repo-grounded track.

## How a case earned sign-off

1. **Drafting + machine gates.** LLM drafting behind schema validators
   (edge-type consistency, reference integrity, info-state containment,
   required-info availability, orphan-info introduction,
   required/inferred disjointness) and lint (terminal reachability,
   stranded nodes, blind-only starts, verification-timing heuristic,
   level consistency, image existence/uniqueness/provenance,
   future-knowledge literals in scoring fields). Drafts that fail are
   repaired in-loop against the same thread.
2. **Adversarial audit** (sampled 10/43 on the wave-1 additions):
   per-case reviewer + independent skeptic, evidence required from both
   graph and thread.
3. **Release sign-off, one reviewer per case**: Claude Fable 5 (11
   cases), Claude Opus 5 (68, including 29 adjudications of advisory
   GPT-5.6 reviews). Sign rule: no high-severity finding and no
   unrepaired medium-severity finding.
4. **Repair + re-sign** for the 26 initially refused: evidence-grounded
   surgery, then an independent re-sign check (GPT-5.6 via the gateway)
   that verified each blocking finding was repaired or decisively
   refuted. All 26 signed after repair.

Sign-off is model-executed, not human-executed. Per-case verdicts,
reviewer identity, and every filed finding (including the ones that did
not block) are recorded in `data/REVIEW_FINDINGS.json` and rendered in
`data/REVIEW.md`. Treat this as machine review of machine-drafted data:
it is auditable, not authoritative.

## What sign-off caught

Defect classes the reviewers found and the corpus was repaired against:

- future-knowledge literals (PR/version identifiers postdating the case)
  inside scoring fields — the dominant class, corpus-wide sweep
- clarification questions naming fix contents (rule 4e(iv))
- verification-timing inversions (post-fix retests placed upstream of
  the fix edge, rewarding verify-before-fix)
- invented fix mechanisms for link-only PRs, and retracted maintainer
  hypotheses scored as the root cause
- measurement-class violations (config-toggle probes modeled as kept
  system changes, creating phantom system states)
- persona-incompatible actions folded into the simulated user
- privacy: the sign-off layer caught scrub defects the pipeline missed —
  display names and mail signatures absent from author fields, handles
  of deleted accounts, private hostnames, filesystem-path usernames, and
  (self-inflicted) pseudonym-cascade and technical-token poisoning from
  an over-broad @-mention pass. See `docs/data-collection-and-privacy.md`.

## Reproducing the pipeline

```
uv run --native-tls python scripts/prepare_github_cases.py --help
uv run --native-tls python scripts/prepare_bugzilla_cases.py --help
uv run --native-tls python scripts/prepare_pgsql_cases.py --help
uv run --native-tls python scripts/scrub.py            # dry run
uv run --native-tls python scripts/validate.py 'data/*/graphs/*.json'
uv run --native-tls python scripts/make_review_docs.py
```

Identity maps and reviewer-filed extra identities live OUTSIDE the
repository (`~/graph_bench_private/`); no credentials, endpoints, or
identity mappings are committed here.
