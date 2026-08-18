"""Export the released corpus in the shape a Hugging Face dataset wants.

Writes a flat JSONL — one row per released case — beside a dataset card,
so the release is a directory you can inspect and diff rather than a
loader script nobody can read. Nothing is uploaded: publishing is a
separate, deliberate act.

    uv run --native-tls python scripts/export_hf.py --out release/hf

Two things this deliberately does NOT do:

* **Flatten the graph.** The graph IS the annotation — nodes, edges,
  authored answers, blind paths, counterfactual variants. It ships as one
  JSON object per row, not exploded into columns that would lose the
  edges. Consumers parse one field; the alternative is a schema nobody
  can round-trip.
* **Bundle the screenshots by default.** They are 605 MB and carry the
  strictest provenance conditions in `DATA_LICENSE.md`. Rows reference
  them by relative path; `--with-images` copies them in for a release
  that has cleared that check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

CARD = """---
license: cc-by-4.0
language:
  - en
task_categories:
  - text-generation
tags:
  - multi-turn
  - diagnosis
  - agent-evaluation
  - execution-free
size_categories:
  - n<1K
---

# {name}

Causal-graph-grounded, **execution-free** evaluation of conversational
debugging agents, built from real public support threads.

{n} released cases across {projects} projects. Each case is a resolved
issue thread annotated as a causal graph: nodes are
(system-state, information-state) pairs, edges are clarifications the
user can answer, solutions with required elements, and attempts the
thread itself falsified. The same graph constrains a leak-safe user
simulator, grounds an execution-free judge, and yields the metrics — so
an agent is scored on the diagnostic conversation, not on a patch.

## What a row contains

| field | |
|---|---|
| `task_id` | stable case id |
| `title`, `body` | the reporter's opening, as the agent first sees it |
| `graph` | the annotation: nodes, edges, clarifications, blind paths, shortcuts (JSON object) |
| `satisfaction_conditions` | what a resolution must establish |
| `persona_hint` | how this reporter writes |
| `source`, `repo`, `created_at` | provenance |
| `n_nodes`, `n_edges`, `n_clarifications`, `n_blind`, `n_images` | shape, for filtering |

## Using it

The evaluation harness lives at the code repository; this dataset is the
corpus it runs on. A case is played by walking the graph: the simulator
speaks only from the current node, an agent's turn is matched against
that node's out-edges, and the judge scores the terminal solution call
against the case's required elements.

## What it is not

* Not an execution benchmark — there is no environment to reproduce, by
  design: the environment-bound problems real users bring (drivers,
  devices, account state) are exactly the ones containerised benchmarks
  must exclude.
* Not a transcript replay — the simulated user is conditioned on its
  current graph position, never on the resolved thread.

## Provenance and licensing

Curation layer (graphs, conditions, persona hints, indices): CC BY 4.0.
Underlying thread text and attachments remain the copyright of their
authors, collected from Mozilla Bugzilla and permissive-license GitHub
projects; usernames are pseudonymised before release. See
`DATA_LICENSE.md` and `docs/data-collection-and-privacy.md` in the code
repository.

## Known limitations

Machine-drafted and machine-reviewed, with the audit trail published.
English-only, open-source projects only. Per-case scores are not stable
across identical runs (mean absolute drift 0.15 of a grade), so no claim
should rest on a single case.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='release/hf')
    parser.add_argument('--name', default='graph_bench')
    parser.add_argument('--with-images', action='store_true')
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    projects: set[str] = set()
    images_copied = 0

    for path in sorted(REPO.glob('data/*/graphs/*.json')):
        task = json.loads(path.read_text())
        if not (task.get('metadata') or {}).get('hitl_reviewed'):
            continue
        source = path.parents[1].name
        raw_path = REPO / f'data/{source}/raw/{path.stem}.json'
        raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
        graph = task['graph']
        clarifications = [
            c for e in graph['edges'] for c in (e.get('clarifications') or [])
        ]
        image_paths = list(task.get('opening_images') or [])
        for node in graph['nodes'].values():
            image_paths += node.get('symptom_images') or []
        for clar in clarifications:
            image_paths += clar.get('images') or []
        # Paths are absolute on the machine that built the corpus; a
        # release must reference them relative to the dataset root.
        rel_images = [
            str(Path(p).relative_to(REPO)) if str(p).startswith(str(REPO))
            else Path(p).name
            for p in image_paths
        ]
        if args.with_images:
            for src, rel in zip(image_paths, rel_images):
                dst = out / rel
                if Path(src).exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    images_copied += 1
        projects.add(raw.get('repo', '') or source)
        rows.append({
            'task_id': task['task_id'],
            'title': task.get('title', ''),
            'body': task.get('body', ''),
            'graph': graph,
            'satisfaction_conditions': task.get('satisfaction_conditions', []),
            'persona_hint': task.get('persona_hint'),
            'source': source,
            'repo': raw.get('repo', ''),
            'created_at': (raw.get('created_at') or '')[:10],
            'n_nodes': len(graph['nodes']),
            'n_edges': len(graph['edges']),
            'n_clarifications': len(clarifications),
            'n_blind': sum(
                1
                for e in graph['edges']
                if (e.get('solution') or {}).get('is_known_blind_path')
            ),
            'n_images': len(rel_images),
            'images': rel_images,
        })

    data_path = out / 'cases.jsonl'
    with data_path.open('w') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    (out / 'README.md').write_text(
        CARD.format(name=args.name, n=len(rows), projects=len(projects))
    )
    size = data_path.stat().st_size / 1e6
    print(
        f'wrote {data_path} ({len(rows)} cases, {size:.1f} MB) and '
        f'{out}/README.md'
    )
    if args.with_images:
        print(f'copied {images_copied} images')
    else:
        print(
            'images referenced by path only — rerun with --with-images once '
            'the attachment provenance check in DATA_LICENSE.md has cleared'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
