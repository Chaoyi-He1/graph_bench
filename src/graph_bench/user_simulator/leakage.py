"""
§13.5 experiment 1: leakage settings A / B / C for the user simulator.

The production profile is C — the speaker sees only the current node's
symptoms + info_state (§8.7). Profiles A and B deliberately re-create
the leaky simulators the paper quantifies against:

- B (CAB-style): the speaker additionally knows the satisfaction
  conditions.
- A (worst case): the speaker additionally knows the full original
  conversation, reconstructed from the graph's canonical path (the
  authored clarification Q/A pairs + solution turns).

Score_A - Score_C = the inflation caused by future-knowledge leakage.
These profiles exist only for that experiment — never report agent
scores measured under A or B.

Only the ONLINE speaker prompt changes; the offline deterministic
renderer stays leak-free under every profile (it never invents text,
so there is nothing for it to leak).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.user_simulator.loader import (
    build_out_edge_index,
    precompute_canonical_edges,
)

if TYPE_CHECKING:
    from graph_bench.oncall_graph.models import Task


def reconstruct_canonical_conversation(
    task: Task, answer_overrides: dict[str, str] | None = None
) -> list[str]:
    """
    Replay the canonical path as "engineer:"/"user:" lines.

    This is the §13.5-A stand-in for the original oncall transcript:
    every authored clarification (question + real answer) and solution
    (intent + concrete example) along the shortest authored path.

    ``answer_overrides`` keeps a combined §13.5-A + §9.6 run coherent:
    the leaked transcript must tell the same story as the live
    clarification replies, or the "user" contradicts itself.
    """
    overrides = answer_overrides or {}
    graph = task.graph
    index = build_out_edge_index(graph)
    canonical = precompute_canonical_edges(graph, index)
    lines: list[str] = []
    node_id = graph.start_node
    seen: set[str] = set()
    while node_id not in seen:
        seen.add(node_id)
        edge = canonical.get(node_id)
        if edge is None:
            break
        for clar in edge.clarifications:
            question = (
                clar.question_patterns[0]
                if clar.question_patterns
                else f'Could you confirm {clar.info_id}?'
            )
            answer = overrides.get(
                clar.info_id, clar.user_answer_in_this_oncall
            )
            lines.append(f'engineer: {question}')
            lines.append(f'user: {answer}')
        if edge.solution is not None:
            proposal = edge.solution.intent
            if edge.solution.concrete_example:
                proposal = f'{proposal} — {edge.solution.concrete_example}'
            lines.append(f'engineer: {proposal}')
            to_node = graph.nodes[edge.to_node]
            reply = (
                'That fixed it, thanks!'
                if to_node.is_terminal
                else '; '.join(to_node.symptoms_visible) or 'I tried it.'
            )
            lines.append(f'user: {reply}')
        node_id = edge.to_node
    return lines


def build_leak_context(
    task: Task,
    profile: str,
    answer_overrides: dict[str, str] | None = None,
) -> dict | None:
    """The extra knowledge the speaker gets under a leaky profile."""
    if profile == 'C':
        return None
    leak: dict = {
        'profile': profile,
        'satisfaction_conditions': list(task.satisfaction_conditions),
    }
    if profile == 'A':
        leak['original_conversation'] = reconstruct_canonical_conversation(
            task, answer_overrides
        )
    return leak
