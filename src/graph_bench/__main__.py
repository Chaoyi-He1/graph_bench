"""Umbrella CLI: python -m graph_bench <group> <command>."""

from __future__ import annotations

import click

from graph_bench.backbone.cli import backbone
from graph_bench.judge.cli import judge
from graph_bench.oncall_graph.cli import oncall_graph
from graph_bench.recorder.cli import recorder
from graph_bench.user_simulator.cli import user_simulator


@click.group()
def main() -> None:
    """graph_bench command groups."""


main.add_command(oncall_graph, name='graph')
main.add_command(user_simulator, name='user-sim')
main.add_command(recorder, name='recorder')
main.add_command(backbone, name='backbone')
main.add_command(judge, name='judge')

if __name__ == '__main__':
    main()
