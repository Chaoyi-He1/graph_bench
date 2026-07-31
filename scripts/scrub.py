"""Pseudonymize identities in raw threads + graphs before public release.

Policy (docs/data-collection-and-privacy.md §5, layer 1-2): sources are
public identified-by-design systems, so the goal is minimization — replace
emails/usernames/real names with role-stable pseudonyms, keep bot accounts,
keep technical content intact. The identity map is written OUTSIDE the
repository for takedown lookup and never committed.

The rewrite is a generic recursive walk over every string in the JSON, so
schema quirks (Bugzilla's duplicate ``creator``/``author``/``attacher``
fields, nested ``flags[].setter``) cannot leak identities through
unenumerated fields. ``creator_detail`` dicts are dropped wholesale.

Usage:  uv run scripts/scrub.py [--apply]   (dry-run prints the plan)
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import click

REPO = Path(__file__).resolve().parent.parent
MAP_DIR = Path.home() / 'graph_bench_private'
_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_REPLY_NAME = re.compile(r'\(In reply to [^)]*?from comment #(\d+)\)')
_BOT_MARKERS = ('bot', 'release-mgmt', 'orangefactor', 'pulsebot', 'ghost')
_DROP_KEYS = {'creator_detail', 'assigned_to_detail', 'cc_detail'}


def _is_bot(handle: str) -> bool:
    return any(m in handle.lower() for m in _BOT_MARKERS)


class CaseMap:
    """Stable identity -> pseudonym assignment within one case."""

    def __init__(self, reporter: str) -> None:
        self.reporter = reporter
        self.map: dict[str, str] = {reporter: 'reporter'}
        self._n = 0

    def add(self, handle: str) -> None:
        if handle and not _is_bot(handle) and handle not in self.map:
            self._n += 1
            self.map[handle] = f'participant{self._n}'

    def scrub_text(self, text: str) -> str:
        # Known handles/emails first (longest first to avoid partial hits),
        # then their local parts, then quoted-reply display names, then any
        # remaining non-bot email.
        for handle in sorted(self.map, key=len, reverse=True):
            text = text.replace(handle, self.map[handle])
            local = handle.split('@')[0]
            if len(local) >= 4:
                text = text.replace(local, self.map[handle])
        text = _REPLY_NAME.sub(r'(In reply to comment #\1)', text)
        return _EMAIL.sub(
            lambda m: m.group(0) if _is_bot(m.group(0)) else '<email-scrubbed>',
            text,
        )

    def scrub_obj(self, obj):  # noqa: ANN001, ANN201
        if isinstance(obj, dict):
            return {
                k: self.scrub_obj(v)
                for k, v in obj.items()
                if k not in _DROP_KEYS
            }
        if isinstance(obj, list):
            return [self.scrub_obj(v) for v in obj]
        if isinstance(obj, str):
            return self.scrub_text(obj)
        return obj


def _collect_handles(obj, keys: tuple[str, ...], cm: CaseMap) -> None:  # noqa: ANN001
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str):
                cm.add(v)
            else:
                _collect_handles(v, keys, cm)
    elif isinstance(obj, list):
        for v in obj:
            _collect_handles(v, keys, cm)


def scrub_raw(path: Path, apply: bool) -> dict:  # noqa: FBT001
    d = json.loads(path.read_text())
    reporter = (
        d['meta']['creator'] if 'meta' in d else d['reporter']
    )
    cm = CaseMap(reporter)
    _collect_handles(
        d, ('creator', 'author', 'attacher', 'setter', 'reporter'), cm
    )
    scrubbed = cm.scrub_obj(d)
    if apply:
        path.write_text(
            json.dumps(scrubbed, ensure_ascii=False, indent=1) + '\n'
        )
    return cm.map


_PSEUDO = re.compile(r'^(reporter|participant\d+)$')


def scrub_graph(path: Path, maps: dict[str, dict], apply: bool) -> int:  # noqa: FBT001
    """Apply every known handle map to graph free text; count hits."""
    text = path.read_text()
    hits = 0
    for m in maps.values():
        for handle, pseudo in m.items():
            for token in {handle, handle.split('@')[0]}:
                if token == pseudo or _PSEUDO.match(token):
                    continue  # identity/no-op from an already-scrubbed map
                if len(token) >= 4 and token in text:
                    hits += text.count(token)
                    text = text.replace(token, pseudo)
    new = _EMAIL.sub(
        lambda mt: mt.group(0) if _is_bot(mt.group(0)) else '<email-scrubbed>',
        text,
    )
    hits += 1 if new != text else 0
    if apply:
        path.write_text(new)
    return hits


@click.command()
@click.option('--apply', is_flag=True, default=False)
def main(apply: bool) -> None:  # noqa: FBT001
    maps: dict[str, dict] = {}
    for p in sorted(REPO.glob('data/*/raw/*.json')):
        if p.name.startswith(('bmo_', 'gh_')):
            maps[p.name] = scrub_raw(p, apply)
            click.echo(f'{p.name}: {len(maps[p.name])} identities')
    for p in sorted(REPO.glob('data/*/graphs/*.json')):
        hits = scrub_graph(p, maps, apply)
        if hits:
            click.echo(f'{p.name}: {hits} graph-text replacements')
    # Selection indices (CSV) may carry emails inside upstream bug titles.
    for p in sorted(REPO.glob('data/*/raw/*.csv')):
        text = p.read_text()
        new = _EMAIL.sub(
            lambda m: m.group(0) if _is_bot(m.group(0)) else '<email-scrubbed>',
            text,
        )
        if new != text:
            click.echo(f'{p.name}: emails scrubbed in index')
            if apply:
                p.write_text(new)
    if apply:
        MAP_DIR.mkdir(exist_ok=True)
        out = MAP_DIR / f'scrub_map_{time.strftime("%Y%m%d_%H%M%S")}.json'
        out.write_text(json.dumps(maps, ensure_ascii=False, indent=1))
        click.echo(f'identity map written OUTSIDE the repo: {out}')
    else:
        click.echo('dry-run only; re-run with --apply to rewrite files')


if __name__ == '__main__':
    main()
