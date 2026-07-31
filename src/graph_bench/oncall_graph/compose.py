"""
Compose two single-problem Tasks into one §8.12 compositional Task.

Three relations (§9.7):

- ``independent`` — A and B coexist; either order works. Modeled as the
  doc's two linearized order branches (A-first and B-first) sharing one
  combined start and one combined terminal — not the full product graph,
  which would explode.
- ``sequential``  — B is masked until A is fixed: A's subgraph first,
  its terminal spliced into B's start.
- ``conflicting`` — fixing one problem alone worsens the other; only a
  composite solution reaches the terminal. Needs an authored
  ``ConflictSpec`` (§8.12: conflicting relations require engineer
  annotation of which solution worsens what).

Mechanics that keep the §12.1 Graph validators satisfied:

- node/edge ids are namespaced per copied branch (``A__``, ``B2__``…);
  ``info_id``s are NOT namespaced — they are the shared cross-graph
  vocabulary (see ``info_registry``).
- when a branch is entered after another branch finished, every node of
  the later copy gains the earlier branch's accumulated ``info_state``
  (adding the same set to both endpoints of every edge preserves the
  containment invariant, and semantically the user already answered
  those questions).
- splices replace the earlier branch's terminal with the later branch's
  start: edges into the dropped terminal are redirected, so no
  unreachable orphan nodes remain.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from graph_bench.oncall_graph.models import (
    Edge,
    Graph,
    Metadata,
    Node,
    Solution,
    Task,
)
from graph_bench.oncall_graph.shortcuts import (
    expand_graph_with_shortcuts,
)

Relation = Literal['independent', 'sequential', 'conflicting']


class ComposeError(Exception):
    """The two tasks cannot be composed as requested."""


class ConflictSpec(BaseModel):
    """
    Engineer-authored annotation for a ``conflicting`` composition.

    ``sol_a_edge_id`` / ``sol_b_edge_id`` name the solution edges (in
    task A / task B respectively) whose isolated application worsens
    the other problem. ``composite_solution`` is the §8.9 combined fix
    that resolves both at once.
    """

    sol_a_edge_id: str
    sol_b_edge_id: str
    worsened_after_a: list[str] = Field(
        default_factory=list,
        description='symptoms_visible once A is fixed but B got worse',
    )
    worsened_after_b: list[str] = Field(default_factory=list)
    composite_solution: dict


def _copy_nodes(
    graph: Graph,
    prefix: str,
    *,
    extra_info: set[str],
    extra_symptoms: list[str],
) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    for node_id, node in graph.nodes.items():
        symptoms = list(node.symptoms_visible)
        if not node.is_terminal:
            symptoms += [s for s in extra_symptoms if s not in symptoms]
        nodes[f'{prefix}{node_id}'] = node.model_copy(
            update={
                # system_state_id gets the branch prefix too: two copies
                # of the same original node live in different composed
                # world-states (B broken vs B fixed), and an unprefixed
                # shared id would make the shortcut auto-generator emit
                # cross-branch teleport edges.
                'system_state_id': f'{prefix}{node.system_state_id}',
                'info_state': sorted(set(node.info_state) | extra_info),
                'symptoms_visible': symptoms,
            }
        )
    return nodes


def _copy_edges(graph: Graph, prefix: str) -> list[Edge]:
    return [
        edge.model_copy(
            update={
                'edge_id': f'{prefix}{edge.edge_id}',
                'from_node': f'{prefix}{edge.from_node}',
                'to_node': f'{prefix}{edge.to_node}',
            }
        )
        for edge in graph.edges
    ]


def _terminal_ids(graph: Graph, prefix: str = '') -> list[str]:
    ids = [
        f'{prefix}{node_id}'
        for node_id, node in graph.nodes.items()
        if node.is_terminal
    ]
    if not ids:
        msg = 'graph has no terminal node'
        raise ComposeError(msg)
    return ids


def _splice(
    nodes: dict[str, Node],
    edges: list[Edge],
    *,
    drop_terminals: list[str],
    redirect_to: str,
) -> None:
    """Redirect every edge into ``drop_terminals`` and drop the nodes."""
    for terminal_id in drop_terminals:
        del nodes[terminal_id]
    dropped = set(drop_terminals)
    for i, edge in enumerate(edges):
        if edge.to_node in dropped:
            edges[i] = edge.model_copy(update={'to_node': redirect_to})


def _chain(
    first: Task,
    second: Task,
    first_prefix: str,
    second_prefix: str,
    *,
    start_extra_info: set[str],
    start_extra_symptoms: list[str],
) -> tuple[dict[str, Node], list[Edge], str, list[str]]:
    """
    Build "solve ``first``, then ``second``" as one spliced chain.

    Returns (nodes, edges, chain_start_id, chain_terminal_ids).
    """
    first_graph = first.graph
    second_graph = second.graph
    first_terminals = _terminal_ids(first_graph)
    # Info accumulated once `first` is done — from its (single-problem)
    # terminal with the richest info_state.
    first_done_info = set().union(
        *(set(first_graph.nodes[t].info_state) for t in first_terminals)
    )

    nodes = _copy_nodes(
        first_graph,
        first_prefix,
        extra_info=start_extra_info,
        extra_symptoms=start_extra_symptoms,
    )
    edges = _copy_edges(first_graph, first_prefix)

    second_extra = start_extra_info | first_done_info
    nodes.update(
        _copy_nodes(
            second_graph,
            second_prefix,
            extra_info=second_extra,
            extra_symptoms=[],
        )
    )
    edges.extend(_copy_edges(second_graph, second_prefix))

    _splice(
        nodes,
        edges,
        drop_terminals=[f'{first_prefix}{t}' for t in first_terminals],
        redirect_to=f'{second_prefix}{second_graph.start_node}',
    )
    return (
        nodes,
        edges,
        f'{first_prefix}{first_graph.start_node}',
        _terminal_ids(second_graph, second_prefix),
    )


def _compose_sequential(task_a: Task, task_b: Task) -> Graph:
    nodes, edges, start, _ = _chain(
        task_a,
        task_b,
        'A__',
        'B__',
        start_extra_info=set(),
        start_extra_symptoms=[],
    )
    return Graph(start_node=start, nodes=nodes, edges=edges)


def _compose_independent(task_a: Task, task_b: Task) -> Graph:
    a_start = task_a.graph.nodes[task_a.graph.start_node]
    b_start = task_b.graph.nodes[task_b.graph.start_node]
    baseline = set(a_start.info_state) | set(b_start.info_state)

    # A-first branch: while fixing A, B's symptoms stay visible.
    a_nodes, a_edges, a_entry, a_finals = _chain(
        task_a,
        task_b,
        'A1__',
        'B2__',
        start_extra_info=baseline,
        start_extra_symptoms=list(b_start.symptoms_visible),
    )
    # B-first branch, mirrored.
    b_nodes, b_edges, b_entry, b_finals = _chain(
        task_b,
        task_a,
        'B1__',
        'A2__',
        start_extra_info=baseline,
        start_extra_symptoms=list(a_start.symptoms_visible),
    )

    nodes = {**a_nodes, **b_nodes}
    edges = [*a_edges, *b_edges]

    # One combined start replacing both branch entries: same info_state
    # as each entry (the shared baseline), symptoms of both problems.
    start_id = 'C0'
    nodes[start_id] = Node(
        system_state_id='S_composed_start',
        info_state=sorted(baseline),
        symptoms_visible=[
            *a_start.symptoms_visible,
            *(
                s
                for s in b_start.symptoms_visible
                if s not in a_start.symptoms_visible
            ),
        ],
        volunteered_info=sorted(
            set(a_start.volunteered_info) | set(b_start.volunteered_info)
        ),
        label='A+B both present',
    )
    for entry in (a_entry, b_entry):
        nodes.pop(entry)
        for i, edge in enumerate(edges):
            update: dict[str, str] = {}
            if edge.from_node == entry:
                update['from_node'] = start_id
            if edge.to_node == entry:  # cycles back to a branch start
                update['to_node'] = start_id
            if update:
                edges[i] = edge.model_copy(update=update)

    # One shared terminal: both orders end with the same accumulated
    # info (union of both problems' terminal info + baseline).
    terminal_info = set().union(
        *(set(nodes[t].info_state) for t in (*a_finals, *b_finals))
    )
    terminal_id = 'NT_composed'
    nodes[terminal_id] = Node(
        system_state_id='S_composed_terminal',
        info_state=sorted(terminal_info),
        is_terminal=True,
        label='A and B both resolved',
    )
    _splice(
        nodes,
        edges,
        drop_terminals=[*a_finals, *b_finals],
        redirect_to=terminal_id,
    )
    return Graph(start_node='C0', nodes=nodes, edges=edges)


def _find_solution(task: Task, edge_id: str) -> Solution:
    for edge in task.graph.edges:
        if edge.edge_id == edge_id:
            if edge.solution is None:
                msg = f'{task.task_id}: edge {edge_id!r} has no solution'
                raise ComposeError(msg)
            return edge.solution
    msg = f'{task.task_id}: edge {edge_id!r} not found'
    raise ComposeError(msg)


def _restrict_required_info(
    solution: Solution, available: set[str]
) -> Solution:
    """
    Drop required_info items the conflict-layer graph cannot gather —
    otherwise the composed case ships with required-but-ungettable info
    (the classic graph-quality defect) and every call judges blind.
    """
    required = solution.required_info
    return solution.model_copy(
        update={
            'required_info': required.model_copy(
                update={
                    'L1': [i for i in required.L1 if i in available],
                    'L2': [i for i in required.L2 if i in available],
                    'L3': [i for i in required.L3 if i in available],
                }
            )
        }
    )


def _compose_conflicting(
    task_a: Task, task_b: Task, spec: ConflictSpec
) -> Graph:
    a_start = task_a.graph.nodes[task_a.graph.start_node]
    b_start = task_b.graph.nodes[task_b.graph.start_node]
    baseline = set(a_start.info_state) | set(b_start.info_state)
    sol_a = _find_solution(task_a, spec.sol_a_edge_id)
    sol_b = _find_solution(task_b, spec.sol_b_edge_id)
    composite = Solution.model_validate(spec.composite_solution)

    nodes: dict[str, Node] = {
        'C0': Node(
            system_state_id='S_conflict_start',
            info_state=sorted(baseline),
            symptoms_visible=[
                *a_start.symptoms_visible,
                *(
                    s
                    for s in b_start.symptoms_visible
                    if s not in a_start.symptoms_visible
                ),
            ],
            volunteered_info=sorted(
                set(a_start.volunteered_info) | set(b_start.volunteered_info)
            ),
            label='A+B both present (conflicting)',
        ),
        'N_A_fixed_B_worse': Node(
            system_state_id='S_a_fixed_b_worse',
            info_state=sorted(baseline),
            symptoms_visible=spec.worsened_after_a
            or ['A 的症状消失了，但 B 的问题更明显了'],  # noqa: RUF001
            label='A fixed, B worse',
        ),
        'N_B_fixed_A_worse': Node(
            system_state_id='S_b_fixed_a_worse',
            info_state=sorted(baseline),
            symptoms_visible=spec.worsened_after_b
            or ['B 的症状消失了，但 A 的问题更明显了'],  # noqa: RUF001
            label='B fixed, A worse',
        ),
        'NT_composed': Node(
            system_state_id='S_composed_terminal',
            info_state=sorted(baseline),
            is_terminal=True,
            label='A and B both resolved',
        ),
    }

    def _edge(
        edge_id: str, from_node: str, to_node: str, solution: Solution
    ) -> Edge:
        return Edge.model_validate(
            {
                'edge_id': edge_id,
                'edge_type': 'solution_only',
                'from': from_node,
                'to': to_node,
                'solution': solution.model_dump(),
            }
        )

    known_blind_a = _restrict_required_info(sol_a, baseline).model_copy(
        update={'is_known_blind_path': True}
    )
    known_blind_b = _restrict_required_info(sol_b, baseline).model_copy(
        update={'is_known_blind_path': True}
    )
    rollback = Solution(
        intent='revert the last change',
        approach_keywords=['rollback', 'revert', '回滚'],
    )
    composite = _restrict_required_info(composite, baseline).model_copy(
        update={'is_composite': True}
    )

    edges = [
        _edge('e_sol_a_only', 'C0', 'N_A_fixed_B_worse', known_blind_a),
        _edge('e_sol_b_only', 'C0', 'N_B_fixed_A_worse', known_blind_b),
        _edge('e_sol_composite', 'C0', 'NT_composed', composite),
        _edge('e_rollback_a', 'N_A_fixed_B_worse', 'C0', rollback),
        _edge('e_rollback_b', 'N_B_fixed_A_worse', 'C0', rollback),
    ]
    return Graph(start_node='C0', nodes=nodes, edges=edges)


def compose_tasks(
    task_a: Task,
    task_b: Task,
    relation: Relation,
    *,
    conflict: ConflictSpec | None = None,
    task_id: str | None = None,
) -> Task:
    if relation == 'conflicting':
        if conflict is None:
            msg = 'conflicting composition needs a ConflictSpec'
            raise ComposeError(msg)
        graph = _compose_conflicting(task_a, task_b, conflict)
    elif relation == 'sequential':
        graph = _compose_sequential(task_a, task_b)
    elif relation == 'independent':
        graph = _compose_independent(task_a, task_b)
    else:  # pragma: no cover - Literal guards this
        msg = f'unknown relation {relation!r}'
        raise ComposeError(msg)

    composed = Task(
        task_id=task_id
        or f'composed_{relation}_{task_a.task_id}__{task_b.task_id}',
        title=f'[{relation}] {task_a.title or task_a.task_id} + '
        f'{task_b.title or task_b.task_id}',
        graph=expand_graph_with_shortcuts(graph),
        satisfaction_conditions=[
            *task_a.satisfaction_conditions,
            *(
                c
                for c in task_b.satisfaction_conditions
                if c not in task_a.satisfaction_conditions
            ),
        ],
        persona_hint=task_a.persona_hint or task_b.persona_hint,
        metadata=Metadata(
            graph_version='v1',
            created_from=(
                f'compose[{relation}]({task_a.task_id}, {task_b.task_id})'
            ),
            hitl_reviewed=False,
        ),
    )
    # Round-trip through validation so splice mistakes fail here, not
    # at load time in a bench run.
    return Task.model_validate(
        composed.model_dump(by_alias=True, exclude_none=True)
    )


def compositional_gap(score_a: float, score_b: float, score_ab: float) -> float:
    """§9.7: max(Score_A, Score_B) - Score_AB. Positive = degradation."""
    return max(score_a, score_b) - score_ab
