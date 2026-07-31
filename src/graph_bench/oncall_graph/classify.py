from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_bench.oncall_graph.models import Edge, Node


def edge_class(edge: Edge) -> str:
    """CSS class for an edge by type/flavor (matches visualize.py palette)."""
    if edge.edge_type == 'clarification_only':
        return 'clarif'
    if edge.edge_type == 'solution_only':
        sol = edge.solution
        if sol is None:
            msg = f'{edge.edge_id}: solution missing on solution_only edge'
            raise ValueError(msg)
        if sol.is_known_blind_path:
            return 'blind'
        if sol.is_shortcut:
            return 'shortcut'
        return 'solution'
    return 'mixed'


def node_class(node_id: str, node: Node, start_node: str) -> str:
    """CSS class for a node; terminal takes precedence over start."""
    if node.is_terminal:
        return 'terminal'
    if node_id == start_node:
        return 'start'
    return 'normal'
