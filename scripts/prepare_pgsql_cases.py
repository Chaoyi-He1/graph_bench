"""pgsql-bugs wave: public web archive -> task graphs.

Same filter/draft stages; source is the pgsql-bugs mailing list's public
HTML archive (monthly index + flat thread pages). Output: data/pgsql_v0/.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

import click

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.pipeline.draft import draft_task, filter_issue  # noqa: E402
from graph_bench.pipeline.pgsql import (  # noqa: E402
    fetch_flat_thread,
    fetch_month_index,
    group_bug_threads,
    save_raw,
    to_thread_dict,
)


def _default_months(n: int = 6) -> list[str]:
    cur = datetime.date.today().replace(day=1)
    months = []
    for _ in range(n):
        cur = (cur - datetime.timedelta(days=1)).replace(day=1)
        months.append(cur.strftime('%Y-%m'))
    return months


@click.command()
@click.option('--months', default='', help='comma list like 2026-05,2026-06')
@click.option('--out', default='data/pgsql_v0', show_default=True)
@click.option('--min-messages', default=8, show_default=True)
@click.option('--min-reporter-replies', default=2, show_default=True)
@click.option('--target', default=3, show_default=True)
def main(
    months: str,
    out: str,
    min_messages: int,
    min_reporter_replies: int,
    target: int,
) -> None:
    out_dir = REPO / out
    raw_dir, graph_dir = out_dir / 'raw', out_dir / 'graphs'
    for d in (raw_dir, graph_dir):
        d.mkdir(parents=True, exist_ok=True)
    month_list = (
        [m.strip() for m in months.split(',') if m.strip()]
        or _default_months()
    )
    click.echo(f'months: {month_list}')
    entries: list[tuple[str, str]] = []
    for m in month_list:
        try:
            got = fetch_month_index(m)
            entries.extend(got)
            click.echo(f'{m}: {len(got)} messages')
        except Exception as exc:  # noqa: BLE001
            click.echo(f'{m}: index failed ({str(exc)[:80]})')
        time.sleep(0.5)
    threads = group_bug_threads(entries)
    click.echo(f'{len(threads)} BUG-numbered threads in window')

    candidates = sorted(
        (
            (t['n_msgs'], bug_no, t)
            for bug_no, t in threads.items()
            if t['n_msgs'] >= min_messages
        ),
        reverse=True,
    )
    click.echo(f'{len(candidates)} threads with >= {min_messages} messages')

    report: dict = {'profiled': {}, 'filtered': {}, 'drafted': []}
    filter_llm = build_chat_client(effort='low', max_tokens=2000)
    draft_llm = build_chat_client(max_tokens=24000)
    for n_msgs, bug_no, meta in candidates:
        if len(report['drafted']) >= target:
            break
        slug = f'pg_bug_{bug_no}'
        graph_path = graph_dir / f'{slug}.json'
        if graph_path.exists():
            report['drafted'].append(slug)
            continue
        try:
            msgs = fetch_flat_thread(meta['root'])
        except Exception as exc:  # noqa: BLE001
            click.echo(f'{slug}: flat fetch failed ({str(exc)[:80]})')
            continue
        if len(msgs) < min_messages:
            continue
        thread = to_thread_dict(bug_no, meta['subject'], meta['root'], msgs)
        keys = thread.get('reporter_match_keys', [])
        rep_replies = sum(
            1
            for c in thread['comments']
            if any(k in c['author'].lower() for k in keys)
        )
        report['profiled'][slug] = {
            'n_messages': len(msgs),
            'reporter_replies': rep_replies,
        }
        if rep_replies < min_reporter_replies:
            continue
        save_raw(thread, raw_dir)
        try:
            verdict = filter_issue(filter_llm, thread)
        except Exception as exc:  # noqa: BLE001
            click.echo(f'{slug}: filter error {str(exc)[:120]}')
            continue
        report['filtered'][slug] = verdict
        click.echo(
            f'{slug} ({len(msgs)} msgs): '
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
            image_dir=out_dir / 'images',
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
        time.sleep(0.5)

    (out_dir / 'report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1)
    )
    click.echo(f'done: {len(report["drafted"])} drafted')


if __name__ == '__main__':
    main()
