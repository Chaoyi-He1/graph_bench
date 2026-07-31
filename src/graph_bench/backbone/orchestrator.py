from __future__ import annotations

from typing import TYPE_CHECKING

from graph_bench.backbone.agent import (
    AgentError,
    UnrecoverableTurn,
)
from graph_bench.backbone.models import AgentTurn, TranscriptMsg
from graph_bench.recorder.recorder import Recorder
from graph_bench.user_simulator.simulator import build_simulator

if TYPE_CHECKING:
    from graph_bench.backbone.agent import Agent
    from graph_bench.backbone.models import BackboneConfig
    from graph_bench.recorder.models import (
        AgentTelemetry,
        RunMeta,
        TestcaseMetrics,
    )

_RECOVERY_MODES = ('normal', 'recover_session', 'replay_history')


async def _respond_with_recovery(
    agent: Agent, turn: AgentTurn
) -> AgentTelemetry:
    last: AgentError | None = None
    for mode in _RECOVERY_MODES:
        try:
            return await agent.respond(turn, mode=mode)
        except AgentError as exc:
            last = exc
    raise UnrecoverableTurn(turn.task_id, turn.turn_index) from last


async def run_testcase(
    task,  # noqa: ANN001  (Task | path; build_simulator accepts both)
    agent: Agent,
    run_meta: RunMeta,
    config: BackboneConfig,
) -> TestcaseMetrics:
    llm = None
    if config.sim_config.online:
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            get_llm,
        )

        llm = get_llm()
    sim = build_simulator(task, config.sim_config, llm=llm)
    task_id = sim.session.task_id
    rec = Recorder(run_meta, task_id, config.out_dir)
    session_id = f'{run_meta.run_id}:{task_id}'

    opening = sim.opening()
    rec.record_opening(opening)
    transcript = [
        TranscriptMsg(
            role='user', text=opening.text, images=list(opening.images)
        )
    ]

    turn = 0
    while not (sim.is_terminal() or sim.is_satisfied()):
        if turn >= config.max_turns:
            break
        turn += 1
        agent_turn = AgentTurn(
            task_id=task_id,
            session_id=session_id,
            turn_index=turn,
            latest_user_text=transcript[-1].text,
            latest_user_images=list(transcript[-1].images),
            transcript=list(transcript),
            workspace=config.workspace_for(task_id),
        )
        tele = await _respond_with_recovery(agent, agent_turn)
        transcript.append(TranscriptMsg(role='agent', text=tele.text))
        user_turn = sim.respond(tele.text)
        rec.record_turn(tele, user_turn)
        transcript.append(
            TranscriptMsg(
                role='user',
                text=user_turn.text,
                images=list(user_turn.images),
            )
        )

    # §11.2 version pinning: record the TASK's actual graph_version,
    # not the BackboneConfig placeholder (which stays 'v1' forever).
    return rec.finalize(sim.session, graph_version=sim.graph_version)
