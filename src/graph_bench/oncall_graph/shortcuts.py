"""
Auto-generate shortcut solution edges per §8.2 of the design doc.

For every non-shortcut `solution_only` edge S with `from=X`, find every
other node Y that shares X's `system_state_id` but has a **proper
subset** of X's `info_state`. For each such Y, emit a shortcut edge
`Y → S.to` carrying the same Solution payload with `is_shortcut=True`
and `shortcut_skipped_info = X.info_state - Y.info_state`.

This is a mechanical, idempotent operation: re-running on a graph that
already contains the shortcuts is a no-op.
"""

from __future__ import annotations

from graph_bench.oncall_graph.models import Edge, Graph


def autogen_shortcut_edges(graph: Graph) -> list[Edge]:
    """
    Return the list of new shortcut edges that should be added to
    `graph`. Does not mutate the input.
    """
    nodes = graph.nodes
    # Track (from, to) pairs already present so we don't duplicate.
    existing: set[tuple[str, str]] = {
        (e.from_node, e.to_node)
        for e in graph.edges
        if e.edge_type == 'solution_only'
    }

    new_edges: list[Edge] = []

    from graph_bench.oncall_graph.rollbacks import (  # noqa: PLC0415
        is_rollback_edge,
    )

    for edge in graph.edges:
        if edge.edge_type != 'solution_only':
            continue
        if edge.solution is None or edge.solution.is_shortcut:
            continue
        if is_rollback_edge(edge):
            # Rollback edges are escape hatches, not solutions worth
            # jumping to from elsewhere — no shortcut variants.
            continue

        anchor = nodes[edge.from_node]
        anchor_info = set(anchor.info_state)
        anchor_sys = anchor.system_state_id

        for cand_id, cand_node in nodes.items():
            if cand_id == edge.from_node:
                continue
            if cand_node.system_state_id != anchor_sys:
                continue
            cand_info = set(cand_node.info_state)
            if not cand_info < anchor_info:  # strict proper subset
                continue
            if (cand_id, edge.to_node) in existing:
                continue

            skipped = sorted(anchor_info - cand_info)
            shortcut_solution = edge.solution.model_copy(
                update={
                    'is_shortcut': True,
                    'shortcut_skipped_info': skipped,
                    # If the original is_known_blind_path was True, the
                    # shortcut variant inherits that — agent jumping
                    # straight to a known-wrong solution is still wrong.
                }
            )
            shortcut_id = f'{edge.edge_id}__shortcut_from_{cand_id}'
            shortcut = Edge.model_validate(
                {
                    'edge_id': shortcut_id,
                    'edge_type': 'solution_only',
                    'from': cand_id,
                    'to': edge.to_node,
                    'comment': (
                        f'Auto-generated shortcut: bypasses '
                        f'{len(skipped)} clarification(s) '
                        f'({", ".join(skipped)})'
                    ),
                    'solution': shortcut_solution.model_dump(),
                }
            )
            new_edges.append(shortcut)
            existing.add((cand_id, edge.to_node))

    return new_edges


def expand_graph_with_shortcuts(graph: Graph) -> Graph:
    """
    Return a new Graph containing all original edges plus auto-generated
    shortcut edges.
    """
    new_shortcuts = autogen_shortcut_edges(graph)
    if not new_shortcuts:
        return graph
    return Graph(
        start_node=graph.start_node,
        nodes=graph.nodes,
        edges=[*graph.edges, *new_shortcuts],
    )
