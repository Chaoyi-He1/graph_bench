from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

from graph_bench.recorder.metrics import (
    compute_aggregate,
    compute_testcase_metrics,
)
from graph_bench.recorder.models import (
    BatchMetrics,
    RunMeta,
    SessionSnapshot,
    TestcaseEntry,
    TurnRecord,
    UserSide,
)
from graph_bench.recorder.reader import load_turns

if TYPE_CHECKING:
    from collections.abc import Callable

    from graph_bench.recorder.models import (
        AgentTelemetry,
        TestcaseMetrics,
    )
    from graph_bench.user_simulator.models import UserTurn
    from graph_bench.user_simulator.state import SimulatorSession


_TERMINAL_REASONS = frozenset(
    {
        'failed_dead_end',
        'premature_satisfaction',
        'forced_walk_to_terminal',
        'terminal_resolved',
    },
)
_SATISFIED_REASONS = frozenset(
    {'terminal_resolved', 'premature_satisfaction'},
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def snapshot_from_session(
    session: SimulatorSession,
    task_id: str,
    graph_version: str = 'v1',
) -> SessionSnapshot:
    reason = session.termination_reason
    return SessionSnapshot(
        task_id=task_id,
        graph_version=graph_version,
        termination_reason=reason,
        is_terminal=reason in _TERMINAL_REASONS,
        is_satisfied=reason in _SATISFIED_REASONS,
        turn_index=session.turn_index,
        visited=list(session.visited),
        revealed_info_ids={
            k: list(v) for k, v in session.revealed_info_ids.items()
        },
        stall_counts=dict(session.stall_counts),
        hitl_queue=list(session.hitl_queue),
    )


def upsert_metrics(
    run_dir: Path,
    run_meta: RunMeta,
    snapshot: SessionSnapshot,
    metrics: TestcaseMetrics,
    *,
    clock: Callable[[], datetime],
) -> None:
    path = run_dir / 'metrics.json'
    lock = FileLock(str(path) + '.lock')
    with lock:
        if path.exists():
            batch = BatchMetrics.model_validate_json(
                path.read_text(encoding='utf-8'),
            )
        else:
            batch = BatchMetrics(
                run_id=run_meta.run_id,
                agent_id=run_meta.agent_id,
                created_at=clock().isoformat(),
            )
        batch.testcases[snapshot.task_id] = TestcaseEntry(
            snapshot=snapshot,
            metrics=metrics,
        )
        batch.aggregate = compute_aggregate(batch.testcases)
        path.write_text(
            batch.model_dump_json(indent=2),
            encoding='utf-8',
        )


class Recorder:
    """
    Streaming, per-testcase trace writer.

    One Recorder per testcase; ``run_meta`` is shared across a run's
    testcases. Appends one JSONL row per turn (flushed immediately) and
    writes ``run.json`` once per run dir.
    """

    def __init__(
        self,
        run_meta: RunMeta,
        task_id: str,
        out_dir: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_meta = run_meta
        self._task_id = task_id
        self._clock = clock or _utcnow
        self.run_dir = Path(out_dir) / run_meta.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.run_dir / f'{task_id}.jsonl'
        self._fh = self.jsonl_path.open('a', encoding='utf-8')
        self._write_run_json_if_absent()

    def _write_run_json_if_absent(self) -> None:
        run_json = self.run_dir / 'run.json'
        if not run_json.exists():
            run_json.write_text(
                self._run_meta.model_dump_json(indent=2),
                encoding='utf-8',
            )

    def _ts(self) -> str:
        return self._clock().isoformat()

    def _append(self, record: TurnRecord) -> None:
        self._fh.write(record.model_dump_json() + '\n')
        self._fh.flush()

    def record_opening(self, user_turn: UserTurn) -> None:
        self._append(
            TurnRecord(
                turn_index=user_turn.event.turn_index,
                agent=None,
                user=UserSide(
                    text=user_turn.text,
                    base_directive=user_turn.base_directive,
                    images=list(user_turn.images),
                ),
                event=user_turn.event,
                ts=self._ts(),
            ),
        )

    def record_turn(
        self,
        agent: AgentTelemetry,
        user_turn: UserTurn,
    ) -> None:
        self._append(
            TurnRecord(
                turn_index=user_turn.event.turn_index,
                agent=agent,
                user=UserSide(
                    text=user_turn.text,
                    base_directive=user_turn.base_directive,
                    images=list(user_turn.images),
                ),
                event=user_turn.event,
                ts=self._ts(),
            ),
        )

    def finalize(
        self,
        session: SimulatorSession,
        *,
        graph_version: str = 'v1',
    ) -> TestcaseMetrics:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()
        snapshot = snapshot_from_session(
            session,
            self._task_id,
            graph_version,
        )
        turns = load_turns(self.jsonl_path)
        metrics = compute_testcase_metrics(turns, snapshot)
        upsert_metrics(
            self.run_dir,
            self._run_meta,
            snapshot,
            metrics,
            clock=self._clock,
        )
        return metrics
