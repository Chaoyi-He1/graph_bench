"""
Auto-generate rollback edges out of blind/decoy destinations.

The design doc's blind-path example pairs every wrong turn with a return
edge (``N0 -> sol_force_update -> N_BAD``, ``N_BAD -> sol_rollback -> N0``)
and lists "Recovery from user error" as a scored dimension. The graph
builder never emitted those return edges, leaving decoy destinations
absorbing: an agent that matched one blind solution could never leave,
and the stall insurance (which walks only canonical out-edges) terminated
the session as ``failed_dead_end``.

This generator emits, for every non-shortcut ``is_known_blind_path``
solution edge ``X -> D``, a paired rollback ``D -> X`` solution edge
(``is_known_blind_path=False`` — undoing a wrong turn is a correct move).
With the rollback in place the decoy gains a canonical out-edge, so both
an agent that proposes to back out AND the stall insurance can return to
the main chain; a wrong turn costs turns instead of the session.

Mechanical and idempotent, mirroring ``shortcuts.py``: re-running on a
graph that already contains the rollbacks is a no-op. Run BEFORE
``expand_graph_with_shortcuts`` (shortcut generation skips rollback
edges as anchors).
"""

from __future__ import annotations

from graph_bench.oncall_graph.models import Edge, Graph

ROLLBACK_COMMENT = 'Auto-generated rollback: undo blind path'

_ROLLBACK_INTENT = '撤销/放弃刚才这个方向的尝试，回到之前的排查状态再换思路。'  # noqa: RUF001
_ROLLBACK_EXAMPLE = '"刚才那个改动先撤掉/这个方向先放下，我们回头看其他线索。"'  # noqa: RUF001


def is_rollback_edge(edge: Edge) -> bool:
    """True iff ``edge`` was produced by this generator."""
    return bool(edge.comment and edge.comment.startswith(ROLLBACK_COMMENT))


def autogen_rollback_edges(graph: Graph) -> list[Edge]:
    """
    Return the rollback edges missing from ``graph``. Does not mutate.

    One rollback per distinct ``(decoy destination, blind source)`` pair;
    skipped when any solution edge (rollback or authored) already runs
    ``D -> X``, and when the blind edge lands on a terminal.
    """
    existing: set[tuple[str, str]] = {
        (e.from_node, e.to_node)
        for e in graph.edges
        if e.edge_type == 'solution_only'
    }

    new_edges: list[Edge] = []
    for edge in graph.edges:
        sol = edge.solution
        if sol is None or sol.is_shortcut or not sol.is_known_blind_path:
            continue
        decoy, source = edge.to_node, edge.from_node
        if decoy == source or graph.nodes[decoy].is_terminal:
            continue
        if (decoy, source) in existing:
            continue
        rollback = Edge.model_validate(
            {
                'edge_id': f'{edge.edge_id}__rollback',
                'edge_type': 'solution_only',
                'from': decoy,
                'to': source,
                'comment': f'{ROLLBACK_COMMENT} {edge.edge_id}',
                'solution': {
                    'intent': _ROLLBACK_INTENT,
                    'approach_keywords': [
                        'rollback',
                        'undo',
                        '回退',
                        '撤销',
                        '换个思路',
                        '放弃这个方向',
                    ],
                    'concrete_example': _ROLLBACK_EXAMPLE,
                    'required_elements_for_full_match': [
                        'mentions_rollback_or_abandon_direction',
                    ],
                    'required_info': {'L1': [], 'L2': [], 'L3': []},
                    'is_composite': False,
                    'composed_of': [],
                    'is_known_blind_path': False,
                    'is_shortcut': False,
                    'shortcut_skipped_info': [],
                },
            }
        )
        new_edges.append(rollback)
        existing.add((decoy, source))
    return new_edges


def expand_graph_with_rollbacks(graph: Graph) -> Graph:
    """Return a new Graph with all missing rollback edges added."""
    new_rollbacks = autogen_rollback_edges(graph)
    if not new_rollbacks:
        return graph
    return Graph(
        start_node=graph.start_node,
        nodes=graph.nodes,
        edges=[*graph.edges, *new_rollbacks],
    )
