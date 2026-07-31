"""pgsql-bugs harvesting via the public web archive (HTML).

The mbox/raw endpoints redirect-loop for anonymous clients, so this uses the
public archive pages instead: the monthly index lists every message, and the
``/message-id/flat/<id>`` view renders a whole thread on one page. Threads
are keyed by the ``BUG #NNNNN`` marker the PostgreSQL bug form puts in the
subject; the first message is the structured report.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

_UA = 'graph-bench-harvest/0.1'
_BUG = re.compile(r'BUG #(\d+)')
_INDEX_LINK = re.compile(r'href="/message-id/([^"]+)"[^>]*>([^<]+)</a>')
_MSG_SPLIT = re.compile(r'<table class="table-sm table-responsive message-header"')
_FROM = re.compile(r'From:</th>\s*<td>([^<]*)', re.DOTALL)
_DATE = re.compile(r'Date:</th>\s*<td>([^<]*)', re.DOTALL)
_CONTENT = re.compile(r'<div class="message-content">(.*?)</div>', re.DOTALL)
_QUOTE_BLOCK = re.compile(r'(?:^&gt;.*\n){4,}', re.MULTILINE)
_TAG = re.compile(r'<[^>]+>')


def _get(url: str) -> str:
    return subprocess.run(
        ['curl', '-fsS', '--max-time', '90', '-A', _UA, url],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def fetch_month_index(yyyy_mm: str) -> list[tuple[str, str]]:
    """Return (message_id, subject) pairs for one archive month."""
    page = _get(f'https://www.postgresql.org/list/pgsql-bugs/{yyyy_mm}/')
    return [
        (mid, html.unescape(subj).strip())
        for mid, subj in _INDEX_LINK.findall(page)
    ]


def group_bug_threads(
    entries: list[tuple[str, str]],
) -> dict[str, dict]:
    """bug_no -> {root: message_id, subject, n_msgs} from index entries."""
    threads: dict[str, dict] = {}
    for mid, subj in entries:
        m = _BUG.search(subj)
        if not m:
            continue
        t = threads.setdefault(
            m.group(1), {'root': mid, 'subject': subj, 'n_msgs': 0}
        )
        t['n_msgs'] += 1
        if not subj.lower().startswith('re:'):
            t['root'] = mid
            t['subject'] = subj
    return threads


def _html_to_text(fragment: str) -> str:
    text = fragment.replace('<br>', '\n').replace('<br/>', '\n')
    text = re.sub(r'</p>\s*<p>', '\n\n', text)
    text = _TAG.sub('', text)
    text = _QUOTE_BLOCK.sub('[quoted earlier message trimmed]\n', text)
    return html.unescape(text).strip()


def fetch_flat_thread(message_id: str) -> list[dict]:
    page = _get(f'https://www.postgresql.org/message-id/flat/{message_id}')
    msgs: list[dict] = []
    chunks = _MSG_SPLIT.split(page)[1:]
    for chunk in chunks:
        frm = _FROM.search(chunk)
        date = _DATE.search(chunk)
        content = _CONTENT.search(chunk)
        if not (frm and content):
            continue
        msgs.append(
            {
                'author': html.unescape(frm.group(1)).strip(),
                'created_at': html.unescape(date.group(1)).strip()
                if date
                else '',
                'body': _html_to_text(content.group(1)),
            }
        )
    return msgs


_LOGGED_BY = re.compile(r'Logged by:\s*(.+)')
_FORM_EMAIL = re.compile(r'Email address:\s*(\S+)')


def real_reporter(first_msg: dict) -> tuple[str, list[str]]:
    """Resolve the actual reporter behind the pgsql bug form.

    Form-submitted reports arrive as 'PG Bug reporting form <noreply...>';
    the human is named in the body ('Logged by:' / 'Email address:', with
    the archive's (at)/(dot) obfuscation). Returns (display, match_keys).
    """
    author = first_msg['author']
    if 'noreply' not in author.lower():
        local = author.split('(at)')[0].split('<')[-1].strip().lower()
        return author, [k for k in (author.lower(), local) if len(k) >= 4]
    body = first_msg['body']
    name = _LOGGED_BY.search(body)
    email = _FORM_EMAIL.search(body)
    display = (name.group(1).strip() if name else 'reporter')
    keys = []
    if name:
        keys.append(name.group(1).strip().lower())
    if email:
        keys.append(email.group(1).split('(at)')[0].strip().lower())
    return display, [k for k in keys if len(k) >= 4]


def to_thread_dict(bug_no: str, subject: str, root: str, msgs: list[dict]) -> dict:
    first = msgs[0]
    reporter, match_keys = real_reporter(first)
    return {
        'reporter_match_keys': match_keys,
        'repo': 'postgresql.org/pgsql-bugs',
        'number': int(bug_no),
        'url': f'https://www.postgresql.org/message-id/flat/{root}',
        'title': subject,
        'state': 'thread',
        'labels': ['pgsql-bugs'],
        'reporter': reporter,
        'created_at': first['created_at'],
        'closed_at': msgs[-1]['created_at'],
        'body': first['body'],
        'comments': msgs[1:],
        'images': [],
        'slug': f'pg_bug_{bug_no}',
    }


def save_raw(thread: dict, raw_dir: Path) -> None:
    (raw_dir / f'{thread["slug"]}.json').write_text(
        json.dumps(thread, ensure_ascii=False, indent=1)
    )
