"""
CLI commands for the oncall-graph component.

Registered as the `oncall-graph` subgroup of the top-level
`graph_bench` CLI:

    python -m graph_bench oncall-graph build  <script.py> [--out path.json]
    python -m graph_bench oncall-graph visualize  <task.json> [--out path.html]

`build` runs a Python script that must define a top-level `task: Task`
and serializes it to JSON (defaults to sibling `.json` of the script).

`visualize` reads a serialized Task JSON and writes a standalone HTML
file with a mermaid diagram and inspector tables.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import click

from graph_bench.oncall_graph.compose import (
    ComposeError,
    ConflictSpec,
    compose_tasks,
    compositional_gap,
)
from graph_bench.oncall_graph.models import Task
from graph_bench.oncall_graph.visualize import write_html


def _load_task_from_script(script_path: Path) -> Task:
    spec = importlib.util.spec_from_file_location('graph_script', script_path)
    if spec is None or spec.loader is None:
        msg = f'cannot import {script_path}'
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules['graph_script'] = module
    spec.loader.exec_module(module)
    task = getattr(module, 'task', None)
    if not isinstance(task, Task):
        msg = f'{script_path} must define top-level `task: Task`'
        raise TypeError(msg)
    return task


@click.group()
def oncall_graph() -> None:
    """Hand-build and visualize causal graphs for oncall conversations."""


@oncall_graph.command()
@click.argument(
    'script', type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    '--out',
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help='Output JSON path (default: same dir, same stem, .json suffix)',
)
def build(script: Path, out: Path | None) -> None:
    """Run a Python graph script and serialize its `task` to JSON."""
    task = _load_task_from_script(script)
    out_path = out or script.with_suffix('.json')
    payload = task.model_dump(by_alias=True, exclude_none=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    click.echo(
        f'wrote {out_path} ({len(task.graph.nodes)} nodes, {len(task.graph.edges)} edges)'
    )


@oncall_graph.command()
@click.argument(
    'task_json', type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    '--out',
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help='Output HTML path (default: same dir, same stem, .html suffix)',
)
def visualize(task_json: Path, out: Path | None) -> None:
    """Render a serialized Task JSON to a standalone HTML page."""
    raw = json.loads(task_json.read_text(encoding='utf-8'))
    task = Task.model_validate(raw)
    out_path = out or task_json.with_suffix('.html')
    write_html(task, out_path)
    click.echo(f'wrote {out_path}')


@oncall_graph.command()
@click.argument(
    'task_a_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    'task_b_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    '--relation',
    required=True,
    type=click.Choice(['independent', 'sequential', 'conflicting']),
)
@click.option(
    '--conflict-spec',
    'conflict_spec_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help='ConflictSpec JSON (required for --relation conflicting).',
)
@click.option(
    '--out',
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
)
@click.option('--task-id', default=None)
def compose(
    task_a_json: Path,
    task_b_json: Path,
    relation: str,
    conflict_spec_json: Path | None,
    out: Path,
    task_id: str | None,
) -> None:
    """Compose two Task JSONs into one §8.12 compositional task."""
    task_a = Task.model_validate_json(task_a_json.read_text(encoding='utf-8'))
    task_b = Task.model_validate_json(task_b_json.read_text(encoding='utf-8'))
    conflict = None
    if conflict_spec_json is not None:
        conflict = ConflictSpec.model_validate_json(
            conflict_spec_json.read_text(encoding='utf-8')
        )
    try:
        composed = compose_tasks(
            task_a,
            task_b,
            relation,  # type: ignore[arg-type]
            conflict=conflict,
            task_id=task_id,
        )
    except ComposeError as exc:
        raise click.ClickException(str(exc)) from exc
    payload = composed.model_dump(by_alias=True, exclude_none=True)
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    click.echo(
        f'wrote {out} ({composed.task_id}: '
        f'{len(composed.graph.nodes)} nodes, '
        f'{len(composed.graph.edges)} edges)'
    )


@oncall_graph.command(name='gap')
@click.option('--score-a', type=float, required=True)
@click.option('--score-b', type=float, required=True)
@click.option('--score-ab', type=float, required=True)
def gap_cmd(score_a: float, score_b: float, score_ab: float) -> None:
    """§9.7 Compositional Gap = max(Score_A, Score_B) - Score_AB."""
    gap = compositional_gap(score_a, score_b, score_ab)
    click.echo(f'compositional_gap: {gap:+.4f}')
    if gap > 0:
        click.echo('positive gap: the agent degrades on the composed problem')
