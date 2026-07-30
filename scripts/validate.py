"""Validate every task graph under data/ and print structural statistics.

Usage:  uv run scripts/validate.py  [glob ...]
Defaults to data/trial/graphs/*.json. Exits non-zero on any invalid graph
or any referenced image path that does not exist on disk.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from tracegraph_bench.models import Task  # noqa: E402


def image_refs(task: Task) -> list[str]:
    refs = list(task.opening_images)
    for node in task.graph.nodes.values():
        refs.extend(node.symptom_images)
    for edge in task.graph.edges:
        for clar in edge.clarifications:
            refs.extend(clar.images)
    return refs


def main() -> int:
    patterns = sys.argv[1:] or [str(REPO / 'data' / 'trial' / 'graphs' / '*.json')]
    paths = sorted(p for pat in patterns for p in glob.glob(pat))
    if not paths:
        print('no graph files matched', file=sys.stderr)
        return 1
    failures = 0
    for path in paths:
        name = Path(path).name
        try:
            task = Task.model_validate(json.loads(Path(path).read_text()))
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f'FAIL  {name}\n  {exc}')
            continue
        g = task.graph
        n_blind = sum(
            1 for e in g.edges if e.solution and e.solution.is_known_blind_path
        )
        n_clar = sum(len(e.clarifications) for e in g.edges)
        n_cf = sum(
            len(c.counterfactual_candidates)
            for e in g.edges
            for c in e.clarifications
        )
        missing = [r for r in image_refs(task) if not (REPO / r).exists()]
        status = 'OK  ' if not missing else 'WARN'
        if missing:
            failures += 1
        print(
            f'{status}  {name}: nodes={len(g.nodes)} edges={len(g.edges)} '
            f'blind={n_blind} clarifications={n_clar} counterfactuals={n_cf} '
            f'terminals={sum(1 for n in g.nodes.values() if n.is_terminal)}'
        )
        for ref in missing:
            print(f'      missing image: {ref}')
    print(f'{len(paths)} graph(s), {failures} failure(s)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
