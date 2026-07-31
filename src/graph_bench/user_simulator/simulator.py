"""
User simulator façade (Stage-1 + Stage-2 orchestrator).

Wires loader → matching → responder → speaker into the
``opening``/``respond`` contract the backbone consumes. Owns no
scoring: it emits raw ``SimEvent`` facts and structural
satisfaction/termination signals only.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from graph_bench.user_simulator.loader import (
    build_out_edge_index,
    distance_to_terminal,
    load_task,
    precompute_canonical_edges,
)
from graph_bench.user_simulator.matching import (
    classify_turn,
    judge_turn_multi,
    match_edge,
    select_advancing_match,
)
from graph_bench.user_simulator.models import (
    BaseResponse,
    EdgeTypeName,
    MatchResult,
    SimEvent,
    SimulatorConfig,
    UserTurn,
)
from graph_bench.user_simulator.responder import Responder
from graph_bench.user_simulator.speaker import Speaker
from graph_bench.user_simulator.state import SimulatorSession

if TYPE_CHECKING:
    from graph_bench.oncall_graph.models import (
        Node,
        Task,
    )

logger = logging.getLogger(__name__)

# ``simulator.py`` lives at
# packages/lynxbase-multiturn-bench/src/graph_bench/
#     user_simulator/simulator.py
# The package root (the ``data/`` sibling of ``src/``) is three
# parents up.
_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_TESTCASES_ROOT = _PACKAGE_ROOT / 'data' / 'testcases'

_SATISFIED_REASONS = frozenset(
    {'terminal_resolved', 'premature_satisfaction'},
)
_TERMINAL_REASONS = frozenset(
    {
        'failed_dead_end',
        'premature_satisfaction',
        'forced_walk_to_terminal',
        'terminal_resolved',
    },
)


def _build_production_anchorer(config: SimulatorConfig, task_id: str):  # noqa: ANN202
    """
    Mine the user-style corpus and build the BM25 anchorer.

    Online only. Resolves the testcases dir from
    ``config.bm25_corpus_name`` under ``<package>/data/testcases``,
    mines user-side utterances from every OTHER task (excluding
    ``task_id``), logs the corpus size as a sanity check (§10), and
    returns a ``Bm25Anchorer``.
    """
    from graph_bench.user_simulator.anchoring import (  # noqa: PLC0415
        Bm25Anchorer,
        mine_user_corpus,
    )

    testcases_dir = _TESTCASES_ROOT / config.bm25_corpus_name
    corpus = mine_user_corpus(testcases_dir, task_id)
    logger.info(
        'user-sim BM25 corpus %r: %d user utterances (excluding %s)',
        config.bm25_corpus_name,
        len(corpus),
        task_id,
    )
    return Bm25Anchorer(corpus)


class UserSimulator:
    """Plays the user against an agent-under-test on one oncall graph."""

    def __init__(
        self,
        task: Task,
        config: SimulatorConfig | None = None,
        *,
        llm=None,  # noqa: ANN001
        anchorer=None,  # noqa: ANN001
    ) -> None:
        self._task = task
        self._config = config or SimulatorConfig()
        self._graph = task.graph
        self._index = build_out_edge_index(self._graph)
        self._distance_map = distance_to_terminal(self._graph)
        self._canonical = precompute_canonical_edges(
            self._graph,
            self._index,
        )
        start = self._graph.start_node
        self._session = SimulatorSession(
            task_id=task.task_id,
            current_node_id=start,
            visited=[start],
        )
        self._responder = Responder(
            self._graph,
            self._index,
            self._canonical,
            self._config,
            self._session,
        )
        if anchorer is None and self._config.online:
            anchorer = _build_production_anchorer(
                self._config,
                task.task_id,
            )
        from graph_bench.user_simulator.leakage import (  # noqa: PLC0415
            build_leak_context,
        )

        if self._config.leak_profile != 'C' and not self._config.online:
            # The offline renderer is deterministic and never invents
            # text, so a leaky profile would silently measure zero
            # inflation — §13.5 experiment 1 needs the online speaker.
            warnings.warn(
                f'leak_profile={self._config.leak_profile} has no effect '
                f'in offline mode',
                stacklevel=2,
            )
        self._speaker = Speaker(
            self._config,
            llm=llm,
            anchorer=anchorer,
            leak_context=build_leak_context(
                task,
                self._config.leak_profile,
                self._config.answer_overrides,
            ),
        )
        self._speaker_llm = llm

    @property
    def session(self) -> SimulatorSession:
        return self._session

    @property
    def graph_version(self) -> str:
        """§11.2: the version this run is evaluated against."""
        return self._task.metadata.graph_version

    def _node(self, node_id: str) -> Node:
        return self._graph.nodes[node_id]

    def opening(self) -> UserTurn:
        start_id = self._graph.start_node
        start = self._node(start_id)
        # Original screenshots the reporter attached up front: the task's
        # opening images plus the start node's symptom evidence. Claimed
        # through the responder's ledger so later turns never re-send them.
        opening_images = self._responder.claim_images(
            [*self._task.opening_images, *start.symptom_images]
        )
        base = BaseResponse(
            directive='opening', payload=None, images=opening_images
        )
        parts: list[str] = []
        if self._task.body:
            parts.append(self._task.body)
        parts.extend(start.symptoms_visible)
        parts.extend(start.volunteered_info)
        rendered = self._speaker.render(
            base,
            node=start,
            persona=self._task.persona_hint,
            history=self._session.history,
        )
        text = rendered if rendered else '\n'.join(parts)
        if self._task.body and self._task.body not in text:
            text = '\n'.join([*parts, text]) if text else '\n'.join(parts)
        event = SimEvent(
            turn_index=0,
            match=MatchResult(type='opening'),
            node_before=start_id,
            node_after=start_id,
        )
        turn = UserTurn(
            text=text,
            base_directive='opening',
            event=event,
            images=opening_images,
        )
        self._session.history.append(turn)
        self._session.sim_events.append(event)
        return turn

    def respond(self, agent_turn: str) -> UserTurn:
        node_id = self._session.current_node_id
        out_edges = self._index.get(node_id, [])
        if self._config.online and self._speaker_llm is not None:
            all_clars = [
                {
                    'info_id': c.info_id,
                    'question_patterns': list(c.question_patterns),
                }
                for edge in self._graph.edges
                for c in edge.clarifications
            ]
            sol_edges = [
                e for e in out_edges if e.edge_type != 'clarification_only'
            ]
            outcome = judge_turn_multi(
                agent_turn,
                clarifications=all_clars,
                solution_edges=sol_edges,
                llm=self._speaker_llm,
            )
            if outcome.intent == 'clarification' and outcome.clar_match:
                match = outcome.clar_match
            else:
                match = select_advancing_match(
                    outcome.proposals,
                    sol_edges,
                    self._distance_map,
                    self._config.advance_match_threshold,
                )
        else:
            components = classify_turn(
                agent_turn,
                online=self._config.online,
                llm=self._speaker_llm,
            )
            if components.has_clarification and components.has_solution:
                edge_type: EdgeTypeName = 'mixed'
            elif components.has_solution:
                edge_type = 'solution_only'
            else:
                edge_type = 'clarification_only'
            typed_edges = [e for e in out_edges if e.edge_type == edge_type]
            match = match_edge(
                agent_turn,
                edge_type,
                typed_edges,
                online=self._config.online,
                llm=self._speaker_llm,
            )
        base, event = self._responder.respond(match, agent_turn)
        node_after = self._node(self._session.current_node_id)
        text = self._speaker.render(
            base,
            node=node_after,
            persona=self._task.persona_hint,
            history=self._session.history,
        )
        self._session.turn_index += 1
        event.turn_index = self._session.turn_index
        self._session.revealed_latch = (
            self._session.revealed_latch or event.forced_reveal
        )
        event.revealed_by_simulator = self._session.revealed_latch
        turn = UserTurn(
            text=text,
            base_directive=base.directive,
            event=event,
            images=list(base.images),
        )
        self._session.history.append(turn)
        self._session.sim_events.append(event)
        return turn

    def is_terminal(self) -> bool:
        node = self._node(self._session.current_node_id)
        if node.is_terminal:
            return True
        return self._session.termination_reason in _TERMINAL_REASONS

    def is_satisfied(self) -> bool:
        return self._session.termination_reason in _SATISFIED_REASONS

    def inspect(self) -> dict:
        return {
            'task_id': self._session.task_id,
            'current_node_id': self._session.current_node_id,
            'turn_index': self._session.turn_index,
            'termination_reason': self._session.termination_reason,
            'is_terminal': self.is_terminal(),
            'is_satisfied': self.is_satisfied(),
            'revealed_latch': self._session.revealed_latch,
            'n_events': len(self._session.sim_events),
        }


def build_simulator(
    task_or_path,  # noqa: ANN001
    config: SimulatorConfig | None = None,
    *,
    llm=None,  # noqa: ANN001
) -> UserSimulator:
    from graph_bench.oncall_graph.models import (  # noqa: PLC0415
        Task,
    )

    if isinstance(task_or_path, Task):
        task = task_or_path
    elif isinstance(task_or_path, (str, Path)):
        task = load_task(task_or_path)
    else:
        msg = f'unsupported task_or_path: {type(task_or_path)!r}'
        raise TypeError(msg)
    return UserSimulator(task, config, llm=llm)
