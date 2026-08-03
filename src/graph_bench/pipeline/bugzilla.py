"""Mozilla Bugzilla harvesting (non-UI components wave).

Produces thread dicts in the same shape as ``pipeline.github`` so the
filter/draft stages are shared. Attachment URLs on Bugzilla are server-side
stable, but images are archived at crawl time anyway (uniform policy).
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

_API = 'https://bugzilla.mozilla.org/rest'
_UA = {'User-Agent': 'graph-bench-harvest/0.1'}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def search_bugs(
    components: list[str],
    *,
    min_comments: int = 25,
    created_after: str = '2023-01-01',
    limit: int = 30,
) -> list[dict]:
    comp_q = ''.join(
        f'&component={urllib.parse.quote(c)}' for c in components
    )
    url = (
        f'{_API}/bug?product=Core&resolution=FIXED{comp_q}'
        f'&f1=longdescs.count&o1=greaterthan&v1={min_comments}'
        f'&f2=creation_ts&o2=greaterthan&v2={created_after}'
        f'&f3=short_desc&o3=notsubstring&v3=Intermittent'
        f'&limit={limit}'
        f'&include_fields=id,summary,component,platform,op_sys,creation_time'
    )
    return _get(url)['bugs']


def fetch_thread(bug_id: int) -> dict:
    meta = _get(
        f'{_API}/bug/{bug_id}?include_fields=id,summary,component,platform,'
        f'op_sys,creator,creation_time,cf_last_resolved,keywords,regressed_by'
    )['bugs'][0]
    comments = _get(f'{_API}/bug/{bug_id}/comment')['bugs'][str(bug_id)][
        'comments'
    ]
    atts = _get(f'{_API}/bug/{bug_id}/attachment?exclude_fields=data')['bugs'][
        str(bug_id)
    ]
    return {
        'repo': 'bugzilla.mozilla.org/Core',
        'number': bug_id,
        'url': f'https://bugzilla.mozilla.org/show_bug.cgi?id={bug_id}',
        'title': meta['summary'],
        'state': 'FIXED',
        'labels': [meta.get('component', '')] + list(meta.get('keywords', [])),
        'reporter': meta['creator'],
        'created_at': meta['creation_time'],
        'closed_at': meta.get('cf_last_resolved'),
        'body': comments[0]['text'] if comments else '',
        'comments': [
            {
                'author': c['creator'],
                'created_at': c['creation_time'],
                'body': c['text'],
            }
            for c in comments[1:]
        ],
        '_attachments_meta': [
            {
                'id': a['id'],
                'content_type': a['content_type'],
                'description': a.get('description', ''),
            }
            for a in atts
        ],
    }


def harvest_case(bug_id: int, raw_dir: Path, images_dir: Path) -> dict:
    thread = fetch_thread(bug_id)
    slug = f'bmo_core_{bug_id}'
    images: list[dict] = []
    n = 0
    for a in thread['_attachments_meta']:
        if not a['content_type'].startswith('image'):
            continue
        ext = a['content_type'].split('/')[-1].replace('jpeg', 'jpg')
        dest = images_dir / f'{slug}_att{a["id"]}.{ext}'
        url = f'https://bugzilla.mozilla.org/attachment.cgi?id={a["id"]}'
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                dest.write_bytes(r.read())
            images.append(
                {
                    'where': f'attachment {a["id"]}',
                    'source_url': url,
                    'file': dest.name,
                    'description': a['description'],
                }
            )
            n += 1
            time.sleep(0.4)
        except Exception:  # noqa: BLE001 - attachment loss is non-fatal
            continue
    thread['images'] = images
    thread['slug'] = slug
    # Repo-grounded track: Bugzilla (mozilla.org) cases anchor to the
    # Firefox git mirror at bug-creation time.
    from graph_bench.pipeline.github import (  # noqa: PLC0415
        resolve_base_commit,
    )

    for mirror in ('mozilla-firefox/firefox', 'mozilla/gecko-dev'):
        snap = resolve_base_commit(mirror, thread['created_at'])
        if snap is not None:
            thread['base_commit'] = snap
            break
    (raw_dir / f'{slug}.json').write_text(
        json.dumps(thread, ensure_ascii=False, indent=1)
    )
    return thread
