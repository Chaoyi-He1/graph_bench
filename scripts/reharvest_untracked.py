"""Recovery: re-fetch pristine raws for untracked drafted cases.

A buggy scrub pass ran over untracked (no-git-baseline) raw threads; text
replacements cannot be reverted in place. Every source is re-fetchable, so
this script re-harvests each untracked raw that HAS a drafted graph and
deletes untracked pool raws without one. Existing ``base_commit`` values
are preserved to avoid re-resolving. Run the (fixed) scrub afterwards.

Usage: uv run --native-tls python scripts/reharvest_untracked.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
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

from graph_bench.pipeline import bugzilla, github, pgsql  # noqa: E402


def untracked(sub: str) -> list[Path]:
    out = subprocess.run(
        ['git', 'ls-files', '--others', '--exclude-standard', '--', sub],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line]


def main() -> int:
    graphs = {p.stem for p in REPO.glob('data/*/graphs/*.json')}
    kept = deleted = failed = 0
    if '--all' in sys.argv:
        targets = sorted(REPO.glob('data/*/raw/*.json'))
    else:
        targets = untracked(':(glob)data/*/raw/*.json')
    for raw_path in targets:
        slug = raw_path.stem
        if slug not in graphs:
            raw_path.unlink()
            deleted += 1
            continue
        old = json.loads(raw_path.read_text())
        base_commit = old.get('base_commit')
        raw_dir = raw_path.parent
        img_dir = raw_dir.parent / 'images'
        try:
            if slug.startswith('gh_'):
                thread = github.harvest_case(
                    old['repo'], old['number'], raw_dir, img_dir
                )
            elif slug.startswith('bmo_'):
                thread = bugzilla.harvest_case(
                    int(slug.rsplit('_', 1)[1]), raw_dir, img_dir
                )
            elif slug.startswith('pg_'):
                root = old['url'].rstrip('/').rsplit('/', 1)[1]
                msgs = pgsql.fetch_flat_thread(root)
                thread = pgsql.to_thread_dict(
                    str(old['number']), old['title'], root, msgs
                )
                if base_commit:
                    thread['base_commit'] = base_commit
                pgsql.save_raw(thread, raw_dir)
            else:
                print(f'{slug}: unknown source — left as-is')
                continue
            if base_commit and 'base_commit' not in thread:
                thread['base_commit'] = base_commit
                raw_path.write_text(
                    json.dumps(thread, ensure_ascii=False, indent=1)
                )
            kept += 1
            print(f'{slug}: re-fetched')
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f'{slug}: FAILED ({str(exc)[:100]})')
        time.sleep(0.6)
    print(f'\nre-fetched={kept} pool-deleted={deleted} failed={failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
