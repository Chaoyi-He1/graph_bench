from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

from graph_bench.judge.models import (
    BatchJudgments,
    RubricSet,
    RubricVerdict,
    StubBackend,
    TestcaseJudgment,
)
from graph_bench.judge.rubrics import judge_all, resolve_tiers
from graph_bench.judge.scorer import aggregate, combine
from graph_bench.recorder.reader import load_run

if TYPE_CHECKING:
    from graph_bench.judge.models import JudgeBackend, JudgeConfig

logger = logging.getLogger(__name__)

# A judge failure used to be logged and dropped. On a 229-case row that
# silently removed whole cases from the reported grade — and the losses
# were not outcome-neutral: both cases dropped from the first main-table
# row were `terminal_resolved`, i.e. successes, lost to one 502 from the
# gateway. Transient infrastructure must not decide which cases count.
_JUDGE_ATTEMPTS = 3
_JUDGE_BACKOFF_S = 20


def _abstain(task_id: str) -> TestcaseJudgment:
    v = RubricVerdict(score=0.0, label='abstain', rationale='agent_failed')
    return TestcaseJudgment(
        task_id=task_id,
        rubrics=RubricSet(
            proactiveness=v,
            hallucination=v,
            explanation=v,
            recovery=v,
        ),
        grade=0.0,
        grade_components={'abstain': True},
    )


def _judged_task_ids(run_dir: Path) -> set[str]:
    path = run_dir / 'judgments.json'
    if not path.exists():
        return set()
    return set(
        BatchJudgments.model_validate_json(
            path.read_text(encoding='utf-8'),
        ).testcases,
    )


def _upsert(
    run_dir: Path,
    run_id: str,
    model: str,
    judgment: TestcaseJudgment,
    created_at: str,
) -> None:
    path = run_dir / 'judgments.json'
    lock = FileLock(str(path) + '.lock')
    with lock:
        if path.exists():
            batch = BatchJudgments.model_validate_json(
                path.read_text(encoding='utf-8'),
            )
        else:
            batch = BatchJudgments(
                run_id=run_id,
                judge_model=model,
                created_at=created_at,
            )
        batch.testcases[judgment.task_id] = judgment
        batch.aggregate = aggregate(batch.testcases)
        path.write_text(batch.model_dump_json(indent=2), encoding='utf-8')


async def run(
    run_dir,  # noqa: ANN001  (str | Path)
    config: JudgeConfig,
    backend: JudgeBackend | None = None,
) -> BatchJudgments:
    run_dir = Path(run_dir)
    if backend is None:
        if config.online:
            from graph_bench.judge.provider import (  # noqa: PLC0415
                LLMBackend,
            )

            backend = LLMBackend(config)
        else:
            backend = StubBackend()

    recorded = load_run(run_dir)
    if recorded.metrics is None:
        msg = f'{run_dir}: no metrics.json; cannot judge'
        raise FileNotFoundError(msg)
    done = set() if config.force else _judged_task_ids(run_dir)
    created_at = datetime.now(tz=UTC).isoformat()
    sem = asyncio.Semaphore(config.concurrency)
    metrics = recorded.metrics

    async def _one(task_id: str, attempt: int = 1) -> None:
        retry = 0
        async with sem:
            try:
                turns = recorded.traces.get(task_id, [])
                entry = metrics.testcases[task_id]
                if entry.metrics.termination_reason == 'agent_failed':
                    judgment = _abstain(task_id)
                else:
                    verdicts = await judge_all(
                        turns,
                        entry.metrics,
                        entry.snapshot,
                        backend,
                    )
                    resolutions = await resolve_tiers(
                        turns,
                        entry.metrics,
                        backend,
                    )
                    judgment = combine(
                        task_id,
                        entry.metrics,
                        verdicts,
                        resolutions,
                    )
                _upsert(
                    run_dir,
                    metrics.run_id,
                    config.model,
                    judgment,
                    created_at,
                )
                return
            except Exception as exc:  # one case must not poison the batch
                # A 4xx says the request is wrong and will stay wrong;
                # repeating it three times only spends the gateway. Only
                # server-side and network failures are worth another go.
                status = getattr(exc, 'status_code', None)
                permanent = isinstance(status, int) and 400 <= status < 500 and status != 429
                if permanent:
                    logger.warning(
                        'judge gave up on %s: %s', task_id, exc, exc_info=False
                    )
                    return
                if attempt < _JUDGE_ATTEMPTS:
                    logger.warning(
                        'judge attempt %d failed for %s, retrying',
                        attempt,
                        task_id,
                    )
                    retry = attempt
                else:
                    logger.warning(
                        'judge failed for %s after %d attempts',
                        task_id,
                        _JUDGE_ATTEMPTS,
                        exc_info=True,
                    )
                    return
        # Released the semaphore before sleeping: a gateway hiccup should
        # not hold a judging slot idle while it backs off.
        await asyncio.sleep(_JUDGE_BACKOFF_S * retry)
        await _one(task_id, retry + 1)

    pending = [t for t in metrics.testcases if t not in done]
    await asyncio.gather(*(_one(t) for t in pending))

    path = run_dir / 'judgments.json'
    if not path.exists():
        return BatchJudgments(
            run_id=recorded.run_meta.run_id,
            judge_model=config.model,
            created_at=created_at,
        )
    return BatchJudgments.model_validate_json(path.read_text(encoding='utf-8'))
