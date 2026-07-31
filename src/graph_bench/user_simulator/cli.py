"""
CLI dev-aids for the user_simulator subpackage.

Registered as the ``user-sim`` subgroup of the top-level
``graph_bench`` CLI. These are dev aids only -- the
turn-taking loop and the agent-under-test live in the backbone.

    python -m graph_bench user-sim inspect <task.json>
    python -m graph_bench user-sim replay  <task.json> <turns.txt>
    python -m graph_bench user-sim demo     <task.json>
"""

from __future__ import annotations

from pathlib import Path

import click

from graph_bench.user_simulator.loader import (
    build_out_edge_index,
    load_task,
    precompute_canonical_edges,
)
from graph_bench.user_simulator.simulator import (
    build_simulator,
)


@click.group()
def user_simulator() -> None:
    """Dev aids for the structurally-constrained user simulator."""


@user_simulator.command()
@click.argument(
    'task_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def inspect(task_json: Path) -> None:
    """Print node/edge counts + the canonical-reveal-edge map."""
    try:
        task = load_task(task_json)
    except Exception as exc:
        msg = f'failed to load {task_json}: {exc}'
        raise click.ClickException(msg) from exc
    graph = task.graph
    index = build_out_edge_index(graph)
    canonical = precompute_canonical_edges(graph, index)
    click.echo(f'task_id: {task.task_id}')
    click.echo(f'{len(graph.nodes)} nodes, {len(graph.edges)} edges')
    click.echo(f'start_node: {graph.start_node}')
    click.echo('canonical map:')
    for node_id in sorted(graph.nodes):
        edge = canonical.get(node_id)
        edge_id = edge.edge_id if edge is not None else 'none'
        click.echo(f'  {node_id} -> {edge_id}')


@user_simulator.command()
@click.argument(
    'task_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    'turns_file',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def replay(task_json: Path, turns_file: Path) -> None:
    """Replay a file of agent turns (one per line) offline."""
    try:
        sim = build_simulator(task_json)
    except Exception as exc:
        msg = f'failed to build simulator for {task_json}: {exc}'
        raise click.ClickException(msg) from exc
    opening = sim.opening()
    click.echo(f'user: {opening.text}')
    lines = turns_file.read_text(encoding='utf-8').splitlines()
    for raw in lines:
        agent_turn = raw.strip()
        if not agent_turn:
            continue
        click.echo(f'agent: {agent_turn}')
        user_turn = sim.respond(agent_turn)
        click.echo(f'user: {user_turn.text}')
        if sim.is_terminal() or sim.is_satisfied():
            break
    reason = sim.session.termination_reason
    click.echo(f'termination_reason: {reason}')


@user_simulator.command()
@click.argument(
    'task_json',
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def demo(task_json: Path) -> None:
    """Interactively type agent turns on stdin; print user replies."""
    try:
        sim = build_simulator(task_json)
    except Exception as exc:
        msg = f'failed to build simulator for {task_json}: {exc}'
        raise click.ClickException(msg) from exc
    opening = sim.opening()
    click.echo(f'user: {opening.text}')
    while not (sim.is_terminal() or sim.is_satisfied()):
        try:
            agent_turn = click.prompt('agent', prompt_suffix='> ')
        except (EOFError, click.Abort):
            break
        agent_turn = agent_turn.strip()
        if not agent_turn:
            continue
        user_turn = sim.respond(agent_turn)
        click.echo(f'user: {user_turn.text}')
    click.echo(f'termination_reason: {sim.session.termination_reason}')
