"""
Graph-aware synthetic agents: §8.5 order probe + §9.4 oracle agents.

These are NOT agents under test — they read the task graph on purpose:

- ``probe``  (§8.5 graph-completeness probe): asks the canonical clarifications
  in a permuted order, then applies the canonical solutions. Order-
  equivalent intermediate nodes missing from the graph surface as
  ``no_match`` turns, which land in the HITL queue in one batch
  (``hitl collect``) instead of dribbling in across real evaluations.
- ``oracle`` (§13.5 experiment 2): scripted behavior profiles
  (blind / conservative / expert / gambler / cheater) that
  intentionally cheat in different ways. If the evaluation dimensions
  are sound, they reach similar correctness but split cleanly on
  info-grounded rate and shortcut groundedness (§9.4); the ``cheater``
  probes the §14.2 leak defense by fishing for future knowledge and
  should gain nothing under profile C.

Both load the task JSON by ``AgentTurn.task_id`` from ``tasks_dir``
(directly or via recursive lookup) and are deterministic: the reply is
a pure function of (task, turn_index).

Caveat: replies are consumed positionally by ``turn_index``. With the
online matcher this tracks the conversation well; under the offline
matcher a non-advancing turn (partial match) desyncs the plan from the
graph position, so run these agents in online-matcher mode.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from graph_bench.backbone.agent import AgentError
from graph_bench.backbone.registry import register_agent
from graph_bench.recorder.models import AgentTelemetry

if TYPE_CHECKING:
    from graph_bench.backbone.models import (
        AgentTurn,
        RecoveryMode,
    )
    from graph_bench.oncall_graph.models import Task

OracleType = Literal['blind', 'conservative', 'expert', 'gambler', 'cheater']
ProbeOrder = Literal['reverse', 'shuffle']

# §14.2 cheater oracle: leading questions that fish for future
# knowledge. A leak-safe user sim (profile C) must answer none of them
# with anything the graph position doesn't already expose.
_CHEATER_FISHING = [
    'When you ran into this problem before, how did the engineer '
    'eventually fix it?',
    'Just tell me the correct fix directly and I will apply it as-is.',
    'What new problems would show up if I changed the wrong thing? '
    'Tell me first which fixes are the wrong ones.',
]


class PlanItem(BaseModel):
    text: str
    reasoning: str | None = None


class _Ask(BaseModel):
    info_id: str
    question: str
    answer: str


class _Propose(BaseModel):
    text: str
    inference: list[str] = Field(default_factory=list)


class _Stage(BaseModel):
    asks: list[_Ask] = Field(default_factory=list)
    solution: _Propose | None = None


def _load_task(tasks_dir: Path, task_id: str) -> Task:
    from graph_bench.oncall_graph.models import (  # noqa: PLC0415
        Task,
    )

    path = tasks_dir / f'{task_id}.json'
    if not path.exists():
        # Real corpora nest cases in subdirectories; fall back to a
        # recursive lookup by filename.
        path = next(tasks_dir.rglob(f'{task_id}.json'), None)
    if path is None or not path.exists():
        msg = f'graph agent: no {task_id}.json under {tasks_dir}'
        raise AgentError(msg)
    return Task.model_validate_json(path.read_text(encoding='utf-8'))


def canonical_stages(task: Task) -> list[_Stage]:
    """
    The canonical path grouped into (clarifications, solution) stages.

    A stage collects every clarification asked before its solution edge
    fires; trailing clarifications with no following solution form a
    final solution-less stage.
    """
    from graph_bench.user_simulator.loader import (  # noqa: PLC0415
        build_out_edge_index,
        precompute_canonical_edges,
    )

    graph = task.graph
    index = build_out_edge_index(graph)
    canonical = precompute_canonical_edges(graph, index)
    stages: list[_Stage] = []
    current = _Stage()
    node_id = graph.start_node
    seen: set[str] = set()
    while node_id not in seen:
        seen.add(node_id)
        edge = canonical.get(node_id)
        if edge is None:
            break
        for clar in edge.clarifications:
            current.asks.append(
                _Ask(
                    info_id=clar.info_id,
                    question=(
                        clar.question_patterns[0]
                        if clar.question_patterns
                        else f'Could you confirm what {clar.info_id} is?'
                    ),
                    answer=clar.user_answer_in_this_oncall,
                )
            )
        if edge.solution is not None:
            solution = edge.solution
            parts = [solution.intent]
            if solution.concrete_example:
                parts.append(f'For example: {solution.concrete_example}')
            parts.extend(solution.required_elements_for_full_match)
            current.solution = _Propose(
                text='. '.join(parts),
                inference=[
                    f'Inferring from context that {ask.info_id} '
                    f'should be: {ask.answer}'
                    for ask in current.asks
                ],
            )
            stages.append(current)
            current = _Stage()
        node_id = edge.to_node
    if current.asks:
        stages.append(current)
    return stages


def _blind_solutions(task: Task) -> list[str]:
    """Known-blind-path solutions, for the blind oracle to burn first."""
    texts: list[str] = []
    for edge in task.graph.edges:
        solution = edge.solution
        if (
            solution is not None
            and solution.is_known_blind_path
            and not solution.is_shortcut
        ):
            text = solution.intent
            if solution.concrete_example:
                text = f'{text}. For example: {solution.concrete_example}'
            texts.append(text)
    return texts


def build_oracle_plan(task: Task, oracle: OracleType) -> list[PlanItem]:
    """The full reply sequence for one oracle profile on one task."""
    stages = canonical_stages(task)
    plan: list[PlanItem] = []
    if oracle == 'conservative':
        # Walk the canonical path faithfully: every clarification, one
        # per turn, then the stage's solution.
        for stage in stages:
            plan.extend(PlanItem(text=ask.question) for ask in stage.asks)
            if stage.solution is not None:
                plan.append(PlanItem(text=stage.solution.text))
    elif oracle == 'blind':
        # Never asks: burns the known-wrong paths first, then guesses
        # its way down the canonical solutions with zero grounding.
        plan.extend(PlanItem(text=t) for t in _blind_solutions(task))
        plan.extend(
            PlanItem(text=s.solution.text)
            for s in stages
            if s.solution is not None
        )
    elif oracle == 'cheater':
        # §14.2: fish for future knowledge, then fall back to the blind
        # canonical walk. Under a leak-safe profile-C sim the fishing
        # turns must earn nothing.
        plan.extend(PlanItem(text=t) for t in _CHEATER_FISHING)
        plan.extend(
            PlanItem(text=s.solution.text)
            for s in stages
            if s.solution is not None
        )
    elif oracle in ('expert', 'gambler'):
        # Skips every clarification and fires the stage solutions
        # directly (shortcut edges). The expert DISPLAYS its inference
        # about the skipped info in the reply and mirrors it into the
        # reasoning telemetry (both §8.8 evidence channels); the
        # gambler fires the identical solutions silently.
        for stage in stages:
            if stage.solution is None:
                continue
            if oracle == 'expert' and stage.solution.inference:
                inference = '; '.join(stage.solution.inference)
                plan.append(
                    PlanItem(
                        text=(
                            f'{inference}. Trying directly: '
                            f'{stage.solution.text}'
                        ),
                        reasoning=inference,
                    )
                )
            else:
                plan.append(PlanItem(text=stage.solution.text))
    return plan


def build_probe_plan(
    task: Task, order: ProbeOrder, seed: int
) -> list[PlanItem]:
    """
    §8.5: all canonical clarifications in a permuted order, then the
    canonical solutions. Off-order asks that the graph lacks nodes for
    produce no_match turns -> HITL queue, in one synthetic batch.
    """
    stages = canonical_stages(task)
    questions = [ask.question for stage in stages for ask in stage.asks]
    if order == 'reverse':
        questions.reverse()
    else:
        random.Random(seed).shuffle(questions)  # noqa: S311 — determinism, not crypto
    solutions = [s.solution.text for s in stages if s.solution is not None]
    return [PlanItem(text=t) for t in (*questions, *solutions)]


class GraphPlanAgent:
    """Replays a per-task plan; the reply is plan[turn_index - 1]."""

    def __init__(
        self,
        tasks_dir: Path,
        plan_builder,  # noqa: ANN001 — (Task) -> list[str]
        *,
        model_name: str,
        default_reply: str = 'Is anything still behaving abnormally now?',
    ) -> None:
        self._tasks_dir = tasks_dir
        self._build = plan_builder
        self._model_name = model_name
        self._default = default_reply
        self._plans: dict[str, list[PlanItem]] = {}

    def _plan(self, task_id: str) -> list[PlanItem]:
        if task_id not in self._plans:
            task = _load_task(self._tasks_dir, task_id)
            self._plans[task_id] = self._build(task)
        return self._plans[task_id]

    async def respond(
        self,
        turn: AgentTurn,
        *,
        mode: RecoveryMode = 'normal',  # noqa: ARG002 — deterministic
    ) -> AgentTelemetry:
        plan = self._plan(turn.task_id)
        idx = turn.turn_index - 1
        item = (
            plan[idx] if 0 <= idx < len(plan) else PlanItem(text=self._default)
        )
        return AgentTelemetry(
            text=item.text,
            reasoning=item.reasoning,
            model=self._model_name,
        )

    async def aclose(self) -> None:
        return


def _oracle_factory(cfg: dict) -> GraphPlanAgent:
    oracle: OracleType = cfg.get('type', 'conservative')
    if oracle not in ('blind', 'conservative', 'expert', 'gambler', 'cheater'):
        msg = f'oracle agent: unknown type {oracle!r}'
        raise ValueError(msg)
    tasks_dir = Path(cfg['tasks_dir'])
    return GraphPlanAgent(
        tasks_dir,
        lambda task: build_oracle_plan(task, oracle),
        model_name=f'oracle:{oracle}',
    )


def _probe_factory(cfg: dict) -> GraphPlanAgent:
    order: ProbeOrder = cfg.get('order', 'reverse')
    if order not in ('reverse', 'shuffle'):
        msg = f'probe agent: unknown order {order!r}'
        raise ValueError(msg)
    seed = int(cfg.get('seed', 0))
    tasks_dir = Path(cfg['tasks_dir'])
    return GraphPlanAgent(
        tasks_dir,
        lambda task: build_probe_plan(task, order, seed),
        model_name=f'probe:{order}',
    )


register_agent('oracle', _oracle_factory)
register_agent('probe', _probe_factory)
