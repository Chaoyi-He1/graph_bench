"""End-to-end GitHub testcase preparation (CAB-style stages, graph output).

Usage:
    uv run scripts/prepare_github_cases.py [--repos ...] [--target 10]

Requires GRAPH_BENCH_LLM_BASE_URL / _API_KEY / _MODEL for the filter and
drafting stages. GITHUB_TOKEN is optional (raises rate limits). Stages are
resumable: existing raw threads and graphs are reused.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
from pathlib import Path

import click

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.pipeline.draft import (  # noqa: E402
    draft_task,
    filter_issue,
)
from graph_bench.pipeline.github import harvest_case, search_issues  # noqa: E402

_EXTRA_Q = {
    'flutter/flutter': 'label:"r: fixed" comments:>12 created:>2023-01-01',
}
_DEFAULT_Q = 'comments:>12 created:>2023-01-01'
_BOT_MARKERS = ('[bot]', '-bot', 'github-actions')


def _profile(thread: dict) -> dict:
    humans = [
        c
        for c in thread['comments']
        if not any(m in c['author'] for m in _BOT_MARKERS)
    ]
    rep = sum(1 for c in humans if c['author'] == thread['reporter'])
    return {
        'n_comments': len(thread['comments']),
        'n_human_comments': len(humans),
        'reporter_comments': rep,
        'n_images': len(thread.get('images', [])),
        'participants': len({c['author'] for c in humans}),
    }


@click.command()
@click.option(
    '--repos',
    default='flutter/flutter,expo/expo,home-assistant/core',
    show_default=True,
)
@click.option('--out', default='data/github_v0', show_default=True)
@click.option('--search-limit', default=20, show_default=True)
@click.option('--profile-top', default=7, show_default=True)
@click.option('--target', default=10, show_default=True)
@click.option('--min-reporter', default=3, show_default=True)
def main(
    repos: str,
    out: str,
    search_limit: int,
    profile_top: int,
    target: int,
    min_reporter: int,
) -> None:
    out_dir = REPO / out
    raw_dir = out_dir / 'raw'
    img_dir = out_dir / 'images'
    graph_dir = out_dir / 'graphs'
    for d in (raw_dir, img_dir, graph_dir):
        d.mkdir(parents=True, exist_ok=True)
    report: dict = {'searched': {}, 'profiled': {}, 'filtered': {}, 'drafted': []}

    # Stage 1-2: search + harvest with attachment archiving.
    threads: list[dict] = []
    for repo in repos.split(','):
        repo = repo.strip()
        q = _EXTRA_Q.get(repo, _DEFAULT_Q)
        try:
            items = search_issues(repo, q, limit=search_limit)
        except urllib.error.HTTPError as err:
            click.echo(f'{repo}: search failed ({err}); skipping repo')
            continue
        report['searched'][repo] = len(items)
        click.echo(f'{repo}: {len(items)} candidates')
        picked = 0
        for item in items:
            if picked >= profile_top:
                break
            number = item['number']
            slug = f'gh_{repo.replace("/", "_")}_{number}'
            raw_path = raw_dir / f'{slug}.json'
            try:
                thread = (
                    json.loads(raw_path.read_text())
                    if raw_path.exists()
                    else harvest_case(repo, number, raw_dir, img_dir)
                )
            except urllib.error.HTTPError as err:
                click.echo(f'  #{number}: fetch failed ({err}); stopping repo')
                break
            stats = _profile(thread)
            report['profiled'][slug] = stats
            if stats['reporter_comments'] >= min_reporter:
                thread['stats'] = stats
                threads.append(thread)
                picked += 1
            time.sleep(1.0)

    threads.sort(
        key=lambda t: (t['stats']['n_images'], t['stats']['reporter_comments']),
        reverse=True,
    )
    click.echo(f'{len(threads)} threads pass profiling')

    # Stage 3: LLM issue-level filter (cheap, low effort).
    filter_llm = build_chat_client(effort='low', max_tokens=2000)
    accepted: list[dict] = []
    for thread in threads:
        if len(accepted) >= int(target * 1.5):
            break
        slug = thread['slug']
        try:
            verdict = filter_issue(filter_llm, thread)
        except Exception as exc:  # noqa: BLE001
            click.echo(f'{slug}: filter error {str(exc)[:120]}')
            continue
        report['filtered'][slug] = verdict
        click.echo(
            f'{slug}: {"PASS" if verdict["passed"] else "reject"}'
            f' — {verdict.get("reason", "")[:90]}'
        )
        if verdict['passed']:
            accepted.append(thread)

    # Stage 4-5: graph drafting + validation/repair.
    draft_llm = build_chat_client(max_tokens=24000)
    for thread in accepted:
        if len(report['drafted']) >= target:
            break
        slug = thread['slug']
        graph_path = graph_dir / f'{slug}.json'
        if graph_path.exists():
            report['drafted'].append(slug)
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
            json.dumps(task.model_dump(by_alias=True), ensure_ascii=False, indent=1)
        )
        report['drafted'].append(slug)
        click.echo(f'  -> {graph_path.relative_to(REPO)}')

    (out_dir / 'report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1)
    )
    click.echo(
        f'done: {len(report["drafted"])} drafted, '
        f'{len(report.get("draft_failed", []))} failed; '
        f'report at {out}/report.json'
    )


if __name__ == '__main__':
    main()
