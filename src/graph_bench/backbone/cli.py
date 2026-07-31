from __future__ import annotations

import asyncio
import glob
import os
from datetime import UTC, datetime
from pathlib import Path

import click

from graph_bench.backbone import (  # noqa: F401
    graph_agents,
    scripted_agent,
)
from graph_bench.backbone.models import BackboneConfig
from graph_bench.backbone.registry import get_agent_factory
from graph_bench.backbone.runner import run_batch
from graph_bench.recorder.models import RunMeta
from graph_bench.user_simulator.models import SimulatorConfig


@click.group()
def backbone() -> None:
    """Run an agent against the user simulator + recorder."""


@backbone.command()
@click.option('--agent', 'agent_name', required=True)
@click.option('--tasks', 'tasks_glob', required=True)
@click.option('--run-id', 'run_id', required=True)
@click.option(
    '--out',
    'out_dir',
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
)
@click.option('--concurrency', default=4, show_default=True)
@click.option('--max-turns', 'max_turns', default=20, show_default=True)
@click.option('--online', is_flag=True, default=False, show_default=True)
@click.option(
    '--agent-config',
    'agent_config_json',
    default=None,
    help='Agent factory config as inline JSON '
    '(e.g. \'{"tasks_dir": "...", "type": "expert"}\' for oracle/probe).',
)
@click.option(
    '--sim-config',
    'sim_config_json',
    default=None,
    help='SimulatorConfig field overrides as inline JSON (e.g. '
    '\'{"answer_overrides": {"lynx_version": "0.1"}}\' for §9.6 runs, '
    'or \'{"leak_profile": "A"}\' for §13.5 experiment 1).',
)
def run(
    agent_name: str,
    tasks_glob: str,
    run_id: str,
    out_dir: Path,
    concurrency: int,
    max_turns: int,
    online: bool,  # noqa: FBT001
    agent_config_json: str | None,
    sim_config_json: str | None,
) -> None:
    """Run AGENT over the testcases matching --tasks."""
    import json  # noqa: PLC0415

    task_paths = [Path(p) for p in sorted(glob.glob(tasks_glob))]  # noqa: PTH207
    if not task_paths:
        msg = f'no testcases matched {tasks_glob!r}'
        raise click.ClickException(msg)
    try:
        agent_config = (
            json.loads(agent_config_json) if agent_config_json else {}
        )
        sim_overrides = json.loads(sim_config_json) if sim_config_json else {}
    except json.JSONDecodeError as exc:
        msg = f'invalid inline JSON: {exc}'
        raise click.ClickException(msg) from exc
    # SimulatorConfig ignores unknown fields, so a typo'd key would
    # silently run the wrong experiment — reject instead.
    unknown_keys = set(sim_overrides) - set(SimulatorConfig.model_fields)
    if unknown_keys:
        msg = (
            f'unknown --sim-config key(s): {sorted(unknown_keys)}; '
            f'valid: {sorted(SimulatorConfig.model_fields)}'
        )
        raise click.ClickException(msg)
    config = BackboneConfig(
        run_id=run_id,
        out_dir=out_dir,
        agent_name=agent_name,
        agent_config=agent_config,
        concurrency=concurrency,
        max_turns=max_turns,
        sim_config=SimulatorConfig(
            **{
                'online': online,
                # Opt-in oscillation escape (blind<->rollback thrash ->
                # insurance force-walk). OFF by default so existing runs stay
                # identical; an explicit --sim-config override still wins.
                'count_revisits_toward_stall': (
                    os.environ.get('BENCH_OSCILLATION_STALL') == '1'
                ),
                **sim_overrides,
            }
        ),
    )
    if agent_name == 'api':
        # Importing the submodule runs its register_agent() side effect.
        # Done lazily so offline scripted runs never build an LLM client.
        from graph_bench.agents import api  # noqa: F401, PLC0415
    factory = get_agent_factory(agent_name)
    run_meta = RunMeta(
        run_id=run_id,
        agent_id=agent_name,
        agent_config=config.agent_config,
        sim_config=config.sim_config,
        max_turns=max_turns,
        started_at=datetime.now(tz=UTC).isoformat(),
    )
    sim = config.sim_config
    if sim.leak_profile != 'C' or sim.answer_overrides:
        click.echo(
            f'⚠ EXPERIMENT RUN (leak_profile={sim.leak_profile}, '
            f'answer_overrides={sorted(sim.answer_overrides)}) — '
            f'never report these results as agent scores'
        )
    batch = asyncio.run(run_batch(task_paths, factory, config, run_meta))
    n = len(batch.testcases)
    click.echo(f'ran {n} testcase(s); run dir: {out_dir / run_id}')
