"""Bugzilla non-UI wave: Core networking/JS/storage components -> task graphs.

Same stages as the GitHub pipeline (profile -> LLM filter -> draft ->
validate); source is bugzilla.mozilla.org REST. Output: data/bugzilla_v0/.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.pipeline.bugzilla import harvest_case, search_bugs  # noqa: E402
from graph_bench.pipeline.draft import draft_task, filter_issue  # noqa: E402

_COMPONENTS = [
    'Networking',
    'Networking: HTTP',
    'Networking: Cache',
    'JavaScript Engine',
    'DOM: Workers',
    'DOM: Service Workers',
    'Storage: IndexedDB',
    'XPCOM',
]
_BOTS = ('bot', 'release-mgmt', 'orangefactor', 'pulsebot')


@click.command()
@click.option('--out', default='data/bugzilla_v0', show_default=True)
@click.option('--search-limit', default=40, show_default=True)
@click.option('--profile-top', default=10, show_default=True)
@click.option('--target', default=4, show_default=True)
@click.option('--min-reporter', default=5, show_default=True)
def main(
    out: str, search_limit: int, profile_top: int, target: int, min_reporter: int
) -> None:
    out_dir = REPO / out
    raw_dir, img_dir, graph_dir = (
        out_dir / 'raw',
        out_dir / 'images',
        out_dir / 'graphs',
    )
    for d in (raw_dir, img_dir, graph_dir):
        d.mkdir(parents=True, exist_ok=True)
    report: dict = {'profiled': {}, 'filtered': {}, 'drafted': []}

    candidates = search_bugs(_COMPONENTS, limit=search_limit)
    click.echo(f'{len(candidates)} candidates across non-UI components')
    threads: list[dict] = []
    for item in candidates:
        if len(threads) >= profile_top:
            break
        slug = f'bmo_core_{item["id"]}'
        raw_path = raw_dir / f'{slug}.json'
        try:
            thread = (
                json.loads(raw_path.read_text())
                if raw_path.exists()
                else harvest_case(item['id'], raw_dir, img_dir)
            )
        except Exception as exc:  # noqa: BLE001 - transient BMO 5xx etc.
            click.echo(f'{slug}: harvest failed ({str(exc)[:80]}); skipping')
            time.sleep(3.0)
            continue
        humans = [
            c
            for c in thread['comments']
            if not any(b in c['author'] for b in _BOTS)
        ]
        rep = sum(1 for c in humans if c['author'] == thread['reporter'])
        stats = {
            'component': item['component'],
            'n_comments': len(thread['comments']),
            'reporter_comments': rep,
            'n_images': len(thread.get('images', [])),
        }
        report['profiled'][slug] = stats
        if rep >= min_reporter:
            thread['stats'] = stats
            threads.append(thread)
        time.sleep(1.0)
    click.echo(f'{len(threads)} threads pass profiling')

    filter_llm = build_chat_client(effort='low', max_tokens=2000)
    draft_llm = build_chat_client(max_tokens=24000)
    for thread in threads:
        if len(report['drafted']) >= target:
            break
        slug = thread['slug']
        graph_path = graph_dir / f'{slug}.json'
        if graph_path.exists():
            report['drafted'].append(slug)
            continue
        try:
            verdict = filter_issue(filter_llm, thread)
        except Exception as exc:  # noqa: BLE001
            click.echo(f'{slug}: filter error {str(exc)[:120]}')
            continue
        report['filtered'][slug] = verdict
        click.echo(
            f'{slug} [{thread["stats"]["component"]}]: '
            f'{"PASS" if verdict["passed"] else "reject"} — '
            f'{verdict.get("reason", "")[:80]}'
        )
        if not verdict['passed']:
            continue
        click.echo(f'drafting {slug} …')
        task = draft_task(
            draft_llm,
            thread,
            task_id=slug,
            image_prefix=f'{out}/images',
            image_dir=img_dir,
            log=lambda m: click.echo(m),
        )
        if task is None:
            report.setdefault('draft_failed', []).append(slug)
            continue
        graph_path.write_text(
            json.dumps(
                task.model_dump(by_alias=True), ensure_ascii=False, indent=1
            )
        )
        report['drafted'].append(slug)
        click.echo(f'  -> {graph_path.relative_to(REPO)}')

    (out_dir / 'report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1)
    )
    click.echo(f'done: {len(report["drafted"])} drafted')


if __name__ == '__main__':
    main()
