"""Backfill repo-snapshot commit SHAs for existing cases.

For every raw thread that has a task graph, resolve the default-branch
commit of the (mirror) repository at issue-creation time and record it in
BOTH the raw thread (``base_commit``) and the graph's
``metadata.repo_snapshot``. Anchors the repo-grounded evaluation track.

Mirrors: Bugzilla (mozilla.org) threads map to the Firefox git mirror;
PostgreSQL mailing-list bugs map to the postgres/postgres GitHub mirror.

Usage: uv run --native-tls python scripts/backfill_repo_sha.py [--force]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))


def _load_env(path: Path) -> None:
    """Fill os.environ from a KEY=VALUE .env file (existing vars win)."""
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

from graph_bench.oncall_graph.models import Task  # noqa: E402
from graph_bench.pipeline.github import resolve_base_commit  # noqa: E402

# Non-GitHub sources resolve against public git mirrors (tried in order).
_MIRRORS = {
    'bmo': ['mozilla-firefox/firefox', 'mozilla/gecko-dev'],
    'pg': ['postgres/postgres'],
}


def _target_repos(slug: str, thread: dict) -> list[str]:
    prefix = slug.split('_', 1)[0]
    if prefix == 'gh':
        return [thread['repo']]
    return _MIRRORS.get(prefix, [])


def _created_at(thread: dict) -> str | None:
    """Issue-creation timestamp across harvester shapes.

    Pipeline raws carry a top-level ``created_at``; the hand-piloted trial
    raws are bare Bugzilla REST dumps whose opening comment (count 0)
    carries ``creation_time``.
    """
    if thread.get('created_at'):
        return thread['created_at']
    comments = thread.get('comments') or []
    if comments and comments[0].get('creation_time'):
        return comments[0]['creation_time']
    return None


def main() -> int:
    force = '--force' in sys.argv
    graph_files = sorted(REPO.glob('data/*/graphs/*.json'))
    done = skipped = failed = 0
    for gf in graph_files:
        slug = gf.stem
        raw = next(iter(REPO.glob(f'data/*/raw/{slug}.json')), None)
        if raw is None:
            print(f'{slug}: NO RAW — skipped')
            skipped += 1
            continue
        thread = json.loads(raw.read_text())
        gdata = json.loads(gf.read_text())
        if gdata.get('metadata', {}).get('repo_snapshot') and not force:
            skipped += 1
            continue
        created = _created_at(thread)
        if created is None:
            print(f'{slug}: NO creation timestamp — skipped')
            failed += 1
            continue
        snap = None
        for repo in _target_repos(slug, thread):
            snap = resolve_base_commit(repo, created)
            if snap is not None:
                break
            time.sleep(0.5)
        if snap is None:
            print(f'{slug}: FAILED to resolve base commit')
            failed += 1
            continue
        thread['base_commit'] = snap
        raw.write_text(json.dumps(thread, ensure_ascii=False, indent=1))
        gdata.setdefault('metadata', {})['repo_snapshot'] = snap
        Task.model_validate(gdata)  # never write an invalid graph
        gf.write_text(json.dumps(gdata, ensure_ascii=False, indent=2))
        print(f'{slug}: {snap["repo"]}@{snap["commit_sha"][:12]}')
        done += 1
        time.sleep(0.3)
    print(f'\nbackfilled={done} skipped={skipped} failed={failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
