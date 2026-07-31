from __future__ import annotations

import asyncio
from pathlib import Path

import click

from graph_bench.judge.judge import run as run_judge
from graph_bench.judge.models import JudgeConfig


@click.group()
def judge() -> None:
    """Score a recorded run (LLM rubrics + combined grade)."""


@judge.command()
@click.argument(
    'run_dir',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option('--model', default='stub', show_default=True)
@click.option('--online/--offline', default=False, show_default=True)
@click.option('--concurrency', default=8, show_default=True)
@click.option('--force', is_flag=True, default=False)
def run(
    run_dir: Path,
    model: str,
    online: bool,  # noqa: FBT001
    concurrency: int,
    force: bool,  # noqa: FBT001
) -> None:
    """Judge RUN_DIR; write judgments.json."""
    cfg = JudgeConfig(
        model=model,
        online=online,
        concurrency=concurrency,
        force=force,
    )
    result = asyncio.run(run_judge(run_dir, cfg))
    click.echo(
        f'judged {len(result.testcases)} testcase(s); '
        f'mean_grade={result.aggregate.mean_grade}',
    )
