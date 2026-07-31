"""GitHub REST harvesting with crawl-time attachment archiving.

Unauthenticated by default (60 core req/h); set ``GITHUB_TOKEN`` to raise
limits. Attachment URLs on GitHub redirect to signed S3 links that expire in
minutes — images are always downloaded at crawl time.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

_API = 'https://api.github.com'
_IMG_HOSTS = (
    'user-images.githubusercontent.com',
    'github.com/user-attachments/assets/',
)
_IMG_MD = re.compile(r'!\[[^\]]*\]\((https://[^)\s]+)\)')
_IMG_TAG = re.compile(r'<img[^>]+src="(https://[^"]+)"', re.IGNORECASE)
_IMG_BARE = re.compile(
    r'(https://(?:user-images\.githubusercontent\.com|'
    r'github\.com/user-attachments/assets)/[^\s)\]"<>]+)'
)


def _headers() -> dict[str, str]:
    h = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'graph-bench-harvest/0.1',
    }
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def _get_json(url: str) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r), dict(r.headers)


def search_issues(repo: str, extra_q: str, limit: int = 20) -> list[dict]:
    q = f'repo:{repo} is:issue is:closed {extra_q}'.strip()
    url = (
        f'{_API}/search/issues?q={urllib.parse.quote(q)}'
        f'&sort=comments&order=desc&per_page={limit}'
    )
    data, _ = _get_json(url)
    return data.get('items', [])  # type: ignore[union-attr]


def fetch_thread(repo: str, number: int) -> dict:
    issue, _ = _get_json(f'{_API}/repos/{repo}/issues/{number}')
    comments: list[dict] = []
    page = 1
    while True:
        batch, _ = _get_json(
            f'{_API}/repos/{repo}/issues/{number}/comments'
            f'?per_page=100&page={page}'
        )
        comments.extend(batch)  # type: ignore[arg-type]
        if len(batch) < 100:  # type: ignore[arg-type]
            break
        page += 1
        time.sleep(0.5)
    return {
        'repo': repo,
        'number': number,
        'url': issue['html_url'],  # type: ignore[index]
        'title': issue['title'],  # type: ignore[index]
        'state': issue['state'],  # type: ignore[index]
        'labels': [
            label['name']
            for label in issue.get('labels', [])  # type: ignore[union-attr]
        ],
        'reporter': issue['user']['login'],  # type: ignore[index]
        'created_at': issue['created_at'],  # type: ignore[index]
        'closed_at': issue.get('closed_at'),  # type: ignore[union-attr]
        'body': issue.get('body') or '',  # type: ignore[union-attr]
        'comments': [
            {
                'author': c['user']['login'] if c.get('user') else 'ghost',
                'created_at': c['created_at'],
                'body': c.get('body') or '',
            }
            for c in comments
        ],
    }


def extract_image_urls(text: str) -> list[str]:
    urls: list[str] = []
    for rx in (_IMG_MD, _IMG_TAG, _IMG_BARE):
        urls.extend(rx.findall(text or ''))
    seen: list[str] = []
    for u in urls:
        if any(h in u for h in _IMG_HOSTS) and u not in seen:
            seen.append(u)
    return seen


def download_image(url: str, dest_stem: Path) -> Path | None:
    """Download one attachment; returns the saved path or None."""
    req = urllib.request.Request(url, headers={'User-Agent': 'graph-bench'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            ctype = r.headers.get('Content-Type', '').split(';')[0]
            if not ctype.startswith('image'):
                return None
            ext = mimetypes.guess_extension(ctype) or '.png'
            dest = dest_stem.with_suffix(ext.replace('.jpe', '.jpg'))
            dest.write_bytes(r.read())
            return dest
    except Exception:  # noqa: BLE001 - attachment loss is non-fatal
        return None


def harvest_case(
    repo: str, number: int, raw_dir: Path, images_dir: Path
) -> dict:
    """Fetch a full thread, archive its images, save raw JSON, return it."""
    thread = fetch_thread(repo, number)
    slug = f'gh_{repo.replace("/", "_")}_{number}'
    images: list[dict] = []
    texts = [('opening', thread['body'])] + [
        (f'c{i}', c['body']) for i, c in enumerate(thread['comments'])
    ]
    n = 0
    for where, text in texts:
        for url in extract_image_urls(text):
            dest = download_image(url, images_dir / f'{slug}_img{n}')
            if dest is not None:
                images.append(
                    {'where': where, 'source_url': url, 'file': dest.name}
                )
                n += 1
            time.sleep(0.3)
    thread['images'] = images
    thread['slug'] = slug
    (raw_dir / f'{slug}.json').write_text(
        json.dumps(thread, ensure_ascii=False, indent=1)
    )
    return thread
