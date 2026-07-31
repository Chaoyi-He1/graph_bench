from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from graph_bench.backbone.agent import UnrecoverableTurn
from graph_bench.backbone.orchestrator import run_testcase
from graph_bench.recorder.models import (
    BatchMetrics,
    SessionSnapshot,
    TestcaseMetrics,
)
from graph_bench.recorder.recorder import upsert_metrics
from graph_bench.user_simulator.loader import load_task

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from graph_bench.backbone.agent import Agent
    from graph_bench.backbone.models import BackboneConfig
    from graph_bench.recorder.models import RunMeta


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class RetryLedger:
    """Persistent ``{task_id: attempts}`` across runs (a JSON file)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, int]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding='utf-8'))

    def count(self, task_id: str) -> int:
        return self._load().get(task_id, 0)

    def bump(self, task_id: str) -> int:
        data = self._load()
        data[task_id] = data.get(task_id, 0) + 1
        self._path.write_text(json.dumps(data), encoding='utf-8')
        return data[task_id]

    def exhausted(self, task_id: str, k: int) -> bool:
        return self.count(task_id) >= k


def _finalized_task_ids(run_dir: Path) -> set[str]:
    path = run_dir / 'metrics.json'
    if not path.exists():
        return set()
    batch = BatchMetrics.model_validate_json(
        path.read_text(encoding='utf-8'),
    )
    return set(batch.testcases)


def _write_failed_entry(
    run_dir: Path, run_meta: RunMeta, task_id: str, graph_version: str
) -> None:
    snapshot = SessionSnapshot(
        task_id=task_id,
        graph_version=graph_version,
        termination_reason='agent_failed',
        is_terminal=True,
        is_satisfied=False,
        turn_index=0,
    )
    metrics = TestcaseMetrics(
        task_id=task_id,
        n_turns=0,
        n_agent_turns=0,
        reached_terminal=False,
        termination_reason='agent_failed',
        final_user_satisfaction='none',
    )
    upsert_metrics(
        run_dir,
        run_meta,
        snapshot,
        metrics,
        clock=_utcnow,
    )


async def run_batch(
    task_paths: Sequence[str | Path],
    agent_factory: Callable[[dict], Agent],
    config: BackboneConfig,
    run_meta: RunMeta,
) -> BatchMetrics:
    run_dir = Path(config.out_dir) / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    done = _finalized_task_ids(run_dir)
    ledger = RetryLedger(run_dir / 'retries.json')

    pending: list[str | Path] = []
    for path in task_paths:
        task_id = load_task(path).task_id
        if task_id in done:
            continue
        if ledger.exhausted(task_id, config.max_testcase_retries):
            continue
        pending.append(path)

    sem = asyncio.Semaphore(config.concurrency)

    def _record_failure(task_id: str) -> None:
        if ledger.bump(task_id) >= config.max_testcase_retries:
            _write_failed_entry(
                run_dir, run_meta, task_id, config.graph_version
            )

    async def _one(path: str | Path) -> None:
        async with sem:
            task = load_task(path)
            try:
                agent = agent_factory(config.agent_config)
            except Exception:
                _record_failure(task.task_id)
                return
            try:
                await run_testcase(task, agent, run_meta, config)
            except UnrecoverableTurn:
                _record_failure(task.task_id)
            except Exception:
                # A single testcase crashing (e.g. a transient LLM/network
                # error escaping the sim) must not abort the whole batch:
                # record the failure (retry ledger) and keep the run going.
                logger.exception('testcase %s crashed', task.task_id)
                _record_failure(task.task_id)
            finally:
                await agent.aclose()

    await asyncio.gather(*(_one(p) for p in pending))

    path = run_dir / 'metrics.json'
    if path.exists():
        return BatchMetrics.model_validate_json(
            path.read_text(encoding='utf-8'),
        )
    return BatchMetrics(
        run_id=run_meta.run_id,
        agent_id=run_meta.agent_id,
        created_at=run_meta.started_at,
    )
