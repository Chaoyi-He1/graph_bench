"""
Offline checks for the simulator's two-act turn handling.

No network, no credentials: every assertion runs against the released
graphs through the deterministic backend. Run after touching
``matching.py`` / ``responder.py`` / ``simulator.py``.

    uv run --native-tls python scripts/check_simulator_acts.py

What is guarded here, and why each one exists:

1. DUAL ACT — a turn that proposes a fix AND asks a modeled question is
   matched on the question. Routing such turns to the solution side alone
   made them unmatchable at any node whose out-edges are all
   clarifications, which penalised models that bundle both acts in one
   turn (a style, not a capability) and drove them into forced reveals.
2. RIDE-ALONG ORDER — when the proposal DOES match exactly, the question
   is still answered, but only after the solution call has been graded,
   so asking never retroactively grounds a proposal made without the
   answer.
3. NO FABRICATED RESULT — from a node with no authored solution edge the
   user may not claim an outcome for an unmatched proposal, and the
   persona pass may not put one back in.
4. GAP KIND — a partial still short of an explanation asks for the
   explanation, not for steps the agent already gave.
5. CANONICAL COVERAGE — every non-terminal node is routable, so the stall
   insurance always has something to reveal instead of declaring a
   solvable case a dead end.
"""

from __future__ import annotations

import glob
import sys

sys.path.insert(0, 'src')

from graph_bench.user_simulator.loader import (  # noqa: E402
    _canonical_first_edge,
    build_out_edge_index,
    load_task,
    precompute_canonical_edges,
)
from graph_bench.user_simulator.matching import (  # noqa: E402
    _fallback_outcome,
)
from graph_bench.user_simulator.models import (  # noqa: E402
    BaseResponse,
    MatchResult,
    MultiMatchOutcome,
    ProposalMatch,
    SimulatorConfig,
)
from graph_bench.user_simulator.responder import (  # noqa: E402
    missing_kind,
    partial_followup_draft,
)
from graph_bench.user_simulator.simulator import UserSimulator  # noqa: E402

# Any authored graph exercises the state machine; glob the corpus dirs so
# this runs from a fresh checkout as well as from a materialised release.
GRAPHS = 'data/*/graphs/*.json'


def _sim(task, **cfg):  # noqa: ANN001, ANN003, ANN202
    sim = UserSimulator(
        task, SimulatorConfig(online=False, leak_profile='C', **cfg)
    )
    sim.opening()
    return sim


def check_gap_kind() -> None:
    assert missing_kind(['identifies_corrupt_log_framing']) == 'why'
    assert missing_kind(['rewrites_the_query_to_count_records']) == 'how'
    assert missing_kind(['identifies_x', 'rewrites_y']) == 'both'
    base = MatchResult(
        type='partial',
        edge_type='solution_only',
        subtype='direction_correct_method_missing',
    )
    why = partial_followup_draft(
        base.model_copy(update={'missing_elements': ['identifies_the_cause']})
    )
    how = partial_followup_draft(
        base.model_copy(update={'missing_elements': ['retries_the_migration']})
    )
    assert 'causing' in why and why != how, (why, how)
    print('gap kind            OK')


def check_dual_act_and_no_fabrication() -> None:
    task = None
    for path in sorted(glob.glob(GRAPHS)):
        cand = load_task(path)
        out = [
            e for e in cand.graph.edges if e.from_node == cand.graph.start_node
        ]
        if out and all(e.edge_type == 'clarification_only' for e in out):
            task, out_edges = cand, out
            break
    assert task is not None, 'no clarification-only start node in the corpus'
    question = next(c for e in out_edges for c in e.clarifications)

    sim = _sim(task)
    turn = 'Try setting the cache directory to a local path and restart.'
    reply = sim.respond(turn)
    assert 'tried that' not in reply.text.lower(), reply.text
    assert "haven't run" in reply.text.lower(), reply.text
    print('no fabricated result OK')

    stall_before = dict(sim.session.stall_counts)
    reply = sim.respond(
        f'I suspect storage, so change the mount and retry. '
        f'{question.question_patterns[0]}'
    )
    assert reply.event.match.type == 'exact', reply.event.match
    assert reply.event.match.edge_type == 'clarification_only'
    after = sim.session.stall_counts
    assert sum(after.values()) <= sum(stall_before.values()), (
        f'productive turn stalled: {stall_before} -> {after}'
    )
    print('dual act             OK')

    # The deterministic backend reads both acts out of the same turn too.
    outcome = _fallback_outcome(
        f'{turn} {question.question_patterns[0]}',
        [],
        [
            {
                'info_id': question.info_id,
                'question_patterns': list(question.question_patterns),
            }
        ],
    )
    assert outcome.clar_match is not None
    assert outcome.clar_match.matched_info_ids == [question.info_id]
    print('offline backend      OK')


def check_ride_along_order() -> None:
    for path in sorted(glob.glob(GRAPHS)):
        task = load_task(path)
        out_edges = [
            e for e in task.graph.edges if e.from_node == task.graph.start_node
        ]
        edge = next(
            (
                e
                for e in out_edges
                if e.edge_type == 'solution_only'
                and e.solution
                and e.solution.required_info.L1
            ),
            None,
        )
        if edge is None:
            continue
        question = next(
            (
                c
                for e in task.graph.edges
                for c in e.clarifications
                if c.info_id in edge.solution.required_info.L1
            ),
            None,
        )
        if question is not None:
            break
    sim = _sim(task)
    outcome = MultiMatchOutcome(
        intent='solution',
        clar_match=MatchResult(
            type='exact',
            edge_type='clarification_only',
            matched_info_ids=[question.info_id],
        ),
        proposals=[
            ProposalMatch(
                summary='x', matched_edge_id=edge.edge_id, match_pct=1.0
            )
        ],
    )
    match, ride = sim._combine_acts(  # noqa: SLF001
        outcome, [e for e in out_edges if e.edge_type != 'clarification_only']
    )
    assert match.type == 'exact' and ride == [question.info_id]
    base, event = sim._responder.respond(  # noqa: SLF001
        match, 'agent turn', ride_along_info_ids=ride
    )
    call = event.solution_call
    assert question.info_id not in call.grounding_set, 'graded after the answer'
    assert question.info_id in call.missing_required_info.L1
    assert question.user_answer_in_this_oncall[:25] in base.payload
    assert question.info_id in sim.session.gathered_info_ids
    print('ride-along order     OK')


def check_stall_reset() -> None:
    """
    Under ``reset_stall_on_progress``, a turn that surfaces new
    information clears the node's stall; a re-ask does not. Off by
    default — the flag exists for the ablation, not for production.
    """
    task = None
    for path in sorted(glob.glob(GRAPHS)):
        cand = load_task(path)
        out = [
            e for e in cand.graph.edges if e.from_node == cand.graph.start_node
        ]
        clars = [c for e in out for c in e.clarifications]
        if out and all(e.edge_type == 'clarification_only' for e in out) and (
            len(clars) >= 2
        ):
            task, question = cand, clars[0]
            break
    assert task is not None, 'no multi-clarification start node in the corpus'
    sim = _sim(task, reset_stall_on_progress=True)
    sim.respond('Try clearing the cache and restarting.')
    sim.respond('Try reinstalling the package.')
    node = sim.session.current_node_id
    assert sim.session.stall_counts.get(node) == 2, sim.session.stall_counts
    sim.respond(question.question_patterns[0])
    assert not sim.session.stall_counts.get(node), (
        f'a productive turn must clear the stall: {sim.session.stall_counts}'
    )
    sim.respond(question.question_patterns[0])  # re-ask: no new information
    sim.respond('Try clearing the cache and restarting.')
    assert sim.session.stall_counts.get(sim.session.current_node_id), (
        're-asking an answered question must not shield the node'
    )
    print('stall reset          OK')


def check_not_attempted_guard() -> None:
    """
    The persona pass may restyle a ``not_attempted`` reply but never turn
    it into evidence. Measured drift before this guard: 18 of 29 such
    replies came back claiming an attempt the user never made.
    """
    from graph_bench.user_simulator.speaker import (  # noqa: PLC0415
        _NOT_ATTEMPTED,
        Speaker,
    )

    class _FabricatingLlm:
        def invoke(self, _input):  # noqa: ANN001, ANN202
            return 'I tried that, but nothing changed on my side.'

    class _CleanLlm:
        def invoke(self, _input):  # noqa: ANN001, ANN202
            return "I haven't gotten to that — what else would help?"

    task = load_task(sorted(glob.glob(GRAPHS))[0])
    node = task.graph.nodes[task.graph.start_node]
    base = BaseResponse(
        directive='not_attempted',
        payload=_NOT_ATTEMPTED,
        intent='say you have not run it and report no result',
    )
    cfg = SimulatorConfig(online=True, leak_profile='C')
    fabricated = Speaker(cfg, llm=_FabricatingLlm()).render(
        base, node=node, persona=task.persona_hint, history=[]
    )
    assert fabricated == _NOT_ATTEMPTED, fabricated
    clean = Speaker(cfg, llm=_CleanLlm()).render(
        base, node=node, persona=task.persona_hint, history=[]
    )
    assert clean != _NOT_ATTEMPTED, 'an honest rephrase must survive'
    print('not-attempted guard OK')


def check_opening_is_the_report() -> None:
    """
    The opening turn is exactly the reporter's own words — body, visible
    symptoms, volunteered info — with nothing added. It used to reach the
    persona pass as an empty draft, which the model filled with invented
    filler in 13 of 229 cases.
    """
    class _ChattyLlm:
        def invoke(self, _input):  # noqa: ANN001, ANN202
            return 'Nothing to add.'

    task = load_task(sorted(glob.glob(GRAPHS))[0])
    sim = UserSimulator(
        task,
        SimulatorConfig(online=True, leak_profile='C'),
        llm=_ChattyLlm(),
    )
    opening = sim.opening().text
    start = task.graph.nodes[task.graph.start_node]
    expected = '\n'.join(
        [
            *([task.body] if task.body else []),
            *start.symptoms_visible,
            *start.volunteered_info,
        ]
    )
    assert opening == expected, opening[-200:]
    print('opening fidelity   OK')


def check_canonical_coverage() -> None:
    """
    Every non-terminal node must be routable to a terminal, and a clean
    route must win wherever one exists.

    A node the canonical search cannot route is not merely unrescuable:
    the stall insurance finds no edge, and the case is terminated as a
    dead end with most of its turn budget unspent.
    """
    unroutable: list[str] = []
    demoted: list[str] = []
    nodes = blind_first = 0
    for path in sorted(glob.glob(GRAPHS)):
        task = load_task(path)
        graph = task.graph
        index = build_out_edge_index(graph)
        canonical = precompute_canonical_edges(graph, index)
        for node_id, node in graph.nodes.items():
            if node.is_terminal:
                continue
            nodes += 1
            edge = canonical[node_id]
            if edge is None:
                unroutable.append(f'{task.task_id}:{node_id}')
                continue
            clean = _canonical_first_edge(
                graph, index, node_id, allow_blind=False
            )
            is_blind = (
                edge.solution is not None
                and edge.solution.is_known_blind_path
            )
            blind_first += is_blind
            if clean is not None and edge.edge_id != clean.edge_id:
                demoted.append(f'{task.task_id}:{node_id}')
    assert not unroutable, (
        f'{len(unroutable)} non-terminal nodes have no canonical path '
        f'(insurance would kill these cases): {unroutable[:5]}'
    )
    assert not demoted, (
        f'a clean route existed but was not chosen at: {demoted[:5]}'
    )
    print(
        f'canonical coverage   OK  ({nodes} nodes, '
        f'{blind_first} routed via a blind first hop)'
    )


if __name__ == '__main__':
    check_gap_kind()
    check_dual_act_and_no_fabrication()
    check_ride_along_order()
    check_not_attempted_guard()
    check_opening_is_the_report()
    check_stall_reset()
    check_canonical_coverage()
    print('all simulator act checks passed')
