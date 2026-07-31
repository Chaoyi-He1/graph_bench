from __future__ import annotations

from pathlib import Path

import click

from graph_bench.recorder.metrics import (
    compute_aggregate,
    compute_testcase_metrics,
)
from graph_bench.recorder.reader import (
    RecorderReadError,
    load_run,
    load_turns,
    to_transcript,
)


@click.group()
def recorder() -> None:
    """Dev aids for inspecting recorded benchmark traces."""


@recorder.command()
@click.argument(
    'jsonl',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def show(jsonl: Path) -> None:
    """Pretty-print a trace as an agent/user transcript."""
    try:
        turns = load_turns(jsonl)
    except RecorderReadError as exc:
        raise click.ClickException(str(exc)) from exc
    for line in to_transcript(turns):
        click.echo(f'{line["role"]}: {line["text"]}')


@recorder.command()
@click.argument(
    'jsonl',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def validate(jsonl: Path) -> None:
    """Validate every row; report the count or the first bad line."""
    try:
        turns = load_turns(jsonl, tolerate_partial_tail=False)
    except RecorderReadError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f'ok: {len(turns)} turns validated')


@recorder.command()
@click.argument(
    'run_dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
def metrics(run_dir: Path) -> None:
    """Recompute the deterministic rollup from a run dir's JSONLs."""
    run = load_run(run_dir)
    rows = []
    entries = {}
    for task_id, turns in run.traces.items():
        if run.metrics is not None and task_id in run.metrics.testcases:
            snapshot = run.metrics.testcases[task_id].snapshot
        else:
            click.echo(
                f'{task_id}: no snapshot in metrics.json; skipped',
            )
            continue
        m = compute_testcase_metrics(turns, snapshot)
        entries[task_id] = run.metrics.testcases[task_id]
        rows.append(
            f'{task_id}: turns={m.n_turns} '
            f'grounded_rate={m.info_grounded_decision_rate} '
            f'tiers={m.tier_counts.model_dump()}',
        )
    for row in rows:
        click.echo(row)
    if entries:
        agg = compute_aggregate(entries)
        click.echo(f'aggregate: {agg.model_dump()}')
