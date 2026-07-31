from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from graph_bench.recorder.models import (
    BatchMetrics,
    RunMeta,
    TurnRecord,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


class RecorderReadError(Exception):
    """A recorded trace row failed to parse or validate."""


class RecordedRun(BaseModel):
    run_meta: RunMeta
    metrics: BatchMetrics | None = None
    traces: dict[str, list[TurnRecord]] = Field(default_factory=dict)


def load_turns(
    path: str | Path,
    *,
    tolerate_partial_tail: bool = True,
) -> list[TurnRecord]:
    """
    Load TurnRecords from a JSONL trace.

    A truncated final line (crash-partial write) is dropped when
    ``tolerate_partial_tail``. Any other malformed/invalid row raises
    ``RecorderReadError`` tagged with its 1-based line number.
    """
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines()
    turns: list[TurnRecord] = []
    last_nonempty = max(
        (idx for idx, ln in enumerate(lines, 1) if ln.strip()),
        default=0,
    )
    for i, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            continue
        is_last = i == last_nonempty
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            if is_last and tolerate_partial_tail:
                break
            msg = f'{path}:{i}: invalid JSON'
            raise RecorderReadError(msg) from exc
        try:
            turns.append(TurnRecord.model_validate(obj))
        except ValidationError as exc:
            msg = f'{path}:{i}: invalid TurnRecord: {exc}'
            raise RecorderReadError(msg) from exc
    return turns


def to_transcript(turns: Iterable[TurnRecord]) -> list[dict[str, str]]:
    """Leak-free agent/user transcript: role + text only, in order."""
    out: list[dict[str, str]] = []
    for turn in turns:
        if turn.agent is not None:
            out.append({'role': 'agent', 'text': turn.agent.text})
        out.append({'role': 'user', 'text': turn.user.text})
    return out


def load_run(run_dir: str | Path) -> RecordedRun:
    run_dir = Path(run_dir)
    run_meta = RunMeta.model_validate_json(
        (run_dir / 'run.json').read_text(encoding='utf-8'),
    )
    metrics_path = run_dir / 'metrics.json'
    metrics = (
        BatchMetrics.model_validate_json(
            metrics_path.read_text(encoding='utf-8'),
        )
        if metrics_path.exists()
        else None
    )
    traces = {p.stem: load_turns(p) for p in sorted(run_dir.glob('*.jsonl'))}
    return RecordedRun(run_meta=run_meta, metrics=metrics, traces=traces)
