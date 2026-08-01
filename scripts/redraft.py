"""Re-draft existing LLM cases from their archived raw threads.

Used after prompt/few-shot/validator changes: the prepare_* scripts skip
cases whose graph already exists, so a re-draft must go through here.
Deletes each target graph and drafts it fresh from the raw thread with the
current DRAFT_SYSTEM and validators.

Usage:  uv run scripts/redraft.py [glob ...]
Defaults to every non-trial graph (data/*/graphs minus data/trial).
"""

from __future__ import annotations

import glob as globmod
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))


def _load_env(path: Path) -> None:
    import os  # noqa: PLC0415

    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())


_load_env(REPO / '.env')

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.pipeline.draft import draft_task  # noqa: E402


def main() -> int:
    patterns = sys.argv[1:] or [str(REPO / 'data' / '*' / 'graphs' / '*.json')]
    targets = sorted(
        p
        for pat in patterns
        for p in globmod.glob(pat)
        if '/trial/' not in p
    )
    print(f'{len(targets)} graphs to re-draft')
    llm = build_chat_client(max_tokens=24000)
    ok, failed = [], []
    for gp in targets:
        gp = Path(gp)
        wave_dir = gp.parent.parent  # data/<wave>
        raw = wave_dir / 'raw' / gp.name
        if not raw.exists():
            print(f'{gp.name}: raw thread missing, skipping')
            failed.append(gp.name)
            continue
        thread = json.loads(raw.read_text())
        out_rel = wave_dir.relative_to(REPO).as_posix()
        print(f'redrafting {gp.stem} …', flush=True)
        task = draft_task(
            llm,
            thread,
            task_id=gp.stem,
            image_prefix=f'{out_rel}/images',
            image_dir=wave_dir / 'images',
        )
        if task is None:
            failed.append(gp.name)
            continue
        gp.write_text(
            json.dumps(
                task.model_dump(by_alias=True), ensure_ascii=False, indent=1
            )
        )
        ok.append(gp.name)
        print(f'  -> {gp.relative_to(REPO)}', flush=True)
    print(f'done: {len(ok)} redrafted, {len(failed)} failed: {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
