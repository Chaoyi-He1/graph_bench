from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_bench.oncall_graph import (
        Edge,
        Graph,
        Task,
    )


# ``loader.py`` lives at .../src/graph_bench/user_simulator/;
# the package root (the ``data/`` sibling of ``src/``) is three parents up.
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def _resolve_images(paths: list[str]) -> list[str]:
    """Make package-root-relative image paths absolute (idempotent)."""
    return [
        p if Path(p).is_absolute() else str(_PACKAGE_ROOT / p) for p in paths
    ]


def load_task(json_path: str | Path) -> Task:
    """
    Load a Task from its testcase JSON.

    Deserializes via ``Task.model_validate_json`` and defensively
    expands shortcut edges (idempotent: a graph that already
    contains its shortcuts is returned unchanged). Image attachment
    paths (authored relative to the bench package root) are resolved
    to absolute local paths so every downstream consumer — responder,
    recorder, agent adapters — sees openable files.
    """
    from graph_bench.oncall_graph import Task  # noqa: PLC0415
    from graph_bench.oncall_graph.rollbacks import (  # noqa: PLC0415
        expand_graph_with_rollbacks,
    )
    from graph_bench.oncall_graph.shortcuts import (  # noqa: PLC0415
        expand_graph_with_shortcuts,
    )

    text = Path(json_path).read_text(encoding='utf-8')
    task = Task.model_validate_json(text)
    # Rollbacks first (escape hatches off blind aftermaths), then
    # shortcuts; both are idempotent.
    task.graph = expand_graph_with_rollbacks(task.graph)
    task.graph = expand_graph_with_shortcuts(task.graph)
    task.opening_images = _resolve_images(task.opening_images)
    for node in task.graph.nodes.values():
        node.symptom_images = _resolve_images(node.symptom_images)
    for edge in task.graph.edges:
        for clar in edge.clarifications:
            clar.images = _resolve_images(clar.images)
    return task


def build_info_answer_map(graph: Graph) -> dict[str, str]:
    """
    Map every clarification ``info_id`` to its authored user answer.

    Clarifications live only under edges (``graph.edges[*].clarifications``);
    this flattens them into a node-independent lookup so the responder can
    answer a question matched anywhere in the graph. First occurrence wins.
    """
    answers: dict[str, str] = {}
    for edge in graph.edges:
        for clar in edge.clarifications:
            answers.setdefault(clar.info_id, clar.user_answer_in_this_oncall)
    return answers


def build_info_image_map(graph: Graph) -> dict[str, list[str]]:
    """
    Map every clarification ``info_id`` to its original screenshot paths.

    Companion to :func:`build_info_answer_map` — same flattening and
    first-occurrence-wins rule, but for the ``Clarification.images``
    attachments revealed alongside the answer text.
    """
    images: dict[str, list[str]] = {}
    for edge in graph.edges:
        for clar in edge.clarifications:
            if clar.images:
                images.setdefault(clar.info_id, list(clar.images))
    return images


def build_out_edge_index(graph: Graph) -> dict[str, list[Edge]]:
    """
    Map each node id to the list of its out-edges.

    The substrate stores edges as a flat list with no adjacency
    index; build it once at load. Every node id in ``graph.nodes``
    gets a key (possibly an empty list).
    """
    index: dict[str, list[Edge]] = {nid: [] for nid in graph.nodes}
    for edge in graph.edges:
        index.setdefault(edge.from_node, []).append(edge)
    return index


def _is_canonical_passable(edge: Edge, *, allow_blind: bool = False) -> bool:
    """
    True iff ``edge`` may be traversed by the canonical-path BFS.

    Excludes solution edges that are known blind paths or shortcuts
    (Decision A / §8.4); clarification and plain mixed/solution edges
    pass. ``allow_blind`` re-admits blind paths for the relaxed second
    tier — see ``precompute_canonical_edges``.
    """
    solution = edge.solution
    if solution is None:
        return True
    if solution.is_shortcut:
        return False
    return allow_blind or not solution.is_known_blind_path


def distance_to_terminal(graph: Graph) -> dict[str, int]:
    """
    Min hops from each node to any terminal (reverse BFS). Unreachable
    nodes map to ``1 << 30``; terminals map to ``0``.
    """
    unreachable = 1 << 30
    rev: dict[str, list[str]] = {nid: [] for nid in graph.nodes}
    for edge in graph.edges:
        rev[edge.to_node].append(edge.from_node)
    dist: dict[str, int] = dict.fromkeys(graph.nodes, unreachable)
    queue: deque[str] = deque()
    for nid, node in graph.nodes.items():
        if node.is_terminal:
            dist[nid] = 0
            queue.append(nid)
    while queue:
        cur = queue.popleft()
        for pred in rev[cur]:
            if dist[pred] > dist[cur] + 1:
                dist[pred] = dist[cur] + 1
                queue.append(pred)
    return dist


def _canonical_first_edge(
    graph: Graph,
    index: dict[str, list[Edge]],
    start_id: str,
    *,
    allow_blind: bool,
) -> Edge | None:
    """First edge of the shortest start_id -> terminal path, or None."""
    from collections import deque  # noqa: PLC0415

    first_edge: dict[str, Edge] = {}
    visited: set[str] = {start_id}
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        for edge in index.get(current, []):
            if not _is_canonical_passable(edge, allow_blind=allow_blind):
                continue
            nxt = edge.to_node
            if nxt in visited:
                continue
            first = edge if current == start_id else first_edge[current]
            if graph.nodes[nxt].is_terminal:
                return first
            visited.add(nxt)
            first_edge[nxt] = first
            queue.append(nxt)
    return None


def precompute_canonical_edges(
    graph: Graph, index: dict[str, list[Edge]]
) -> dict[str, Edge | None]:
    """
    Map each node id to the first edge of its canonical path.

    The canonical path is the BFS shortest path from the node to the
    nearest terminal. It is searched in two tiers:

    1. over the subgraph excluding known blind paths and shortcuts;
    2. for nodes the first tier cannot route, over the same subgraph with
       blind paths re-admitted.

    The second tier exists because most real threads reach their fix
    *through* a failed attempt: the only route from an early node to the
    terminal often crosses one blind edge into its aftermath state, from
    which the investigation continues. Refusing to traverse it does not
    protect the agent from a wrong branch — it leaves the node with no
    canonical path at all, so the stall insurance finds nothing to reveal
    and terminates the case as a dead end with most of its turn budget
    unspent. Under tier 1 alone that hit 34% of non-terminal nodes and
    55% of start nodes, and killed about half of every run by turn 5.
    Ordering preserves the original intent: a clean route always wins
    where one exists, and a blind route is used only when the alternative
    is declaring a solvable case unsolvable.

    Shortcuts stay excluded in both tiers: they are planted copies that
    skip authored clarifications, so walking one would hand the agent a
    later state it never worked for.

    The mapped value is the first edge on that path, or ``None`` for
    terminal nodes and for nodes with no route under either tier.
    """
    canonical: dict[str, Edge | None] = {}
    for start_id, node in graph.nodes.items():
        if node.is_terminal:
            canonical[start_id] = None
            continue
        found = _canonical_first_edge(
            graph, index, start_id, allow_blind=False
        )
        if found is None:
            found = _canonical_first_edge(
                graph, index, start_id, allow_blind=True
            )
        canonical[start_id] = found
    return canonical
