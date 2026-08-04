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
_EMAIL = re.compile(
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    # postgresql.org archive obfuscation: user(at)host(dot)tld
    r'|[A-Za-z0-9._%+-]+\(at\)[A-Za-z0-9.-]+(?:\(dot\)[A-Za-z0-9.-]+)+'
)
_REPLY_NAME = re.compile(r'\(In reply to [^)]*?from comment #(\d+)\)')
_BOT_MARKERS = (
    'bot',
    'release-mgmt',
    'orangefactor',
    'pulsebot',
    'ghost',
    'noreply',
)
_DROP_KEYS = {'creator_detail', 'assigned_to_detail', 'cc_detail'}
# High-confidence credential shapes occasionally pasted into public threads
# (GitHub push protection caught a live OpenAI key in an ollama thread).
_SECRETS = re.compile(
    r'sk-[A-Za-z0-9_-]{20,}'
    r'|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|gho_[A-Za-z0-9]{30,}'
    r'|xox[baprs]-[A-Za-z0-9-]{10,}'
    r'|AKIA[0-9A-Z]{16}'
    r'|hf_[A-Za-z0-9]{30,}'
    r'|AIza[0-9A-Za-z_-]{35}'
    r'|lb_[A-Za-z0-9]{24,}'
    r'|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}'
)


# Org/infra account names are not personal identities; mapping them
# corrupts domains ('bugzilla.mozilla.org' -> 'bugzilla.participantN.org').
_ORG_IDENTITIES = {'mozilla', 'firefox', 'bugzilla', 'github', 'postgresql'}

# Handles/local-parts that are bare common words make catastrophic prose
# replacements ('encryption info' -> 'encryption reporter') and identify
# nobody standing alone. They are pseudonymized only when a string field
# IS the identity (author fields), never substituted inside prose.
_COMMON_WORDS = {
    'info', 'admin', 'test', 'user', 'mail', 'root', 'support', 'help',
    'contact', 'hello', 'office', 'sales', 'news', 'team', 'home', 'work',
    'web', 'dev', 'code', 'data', 'image', 'media', 'music', 'video',
    'guest', 'master', 'main', 'debug', 'error', 'crash', 'update',
    'install', 'build', 'server', 'client', 'system', 'network', 'memory',
    'storage', 'windows', 'linux', 'android', 'chrome', 'safari', 'apple',
}


def _prose_safe(token: str) -> bool:
    """False for bare lowercase common words (skip prose substitution)."""
    return not (token.isalpha() and token.islower() and token in _COMMON_WORDS)


# Filesystem paths carry the OS account name, which often differs from any
# collected handle (real-name variants escape handle replacement): mask the
# username segment regardless of the identity map.
_PATH_USER = re.compile(r'(?P<pre>/(?:Users|home)/)(?!<user>)[A-Za-z0-9._-]{2,}')
_WIN_PATH_USER = re.compile(
    r'(?P<pre>[Cc]:\\+Users\\+)(?!<user>)[^\\/"\s]{2,}'
)


def mask_path_users(text: str) -> str:
    text = _PATH_USER.sub(r'\g<pre><user>', text)
    return _WIN_PATH_USER.sub(r'\g<pre><user>', text)


def _is_bot(handle: str) -> bool:
    if handle.lower().strip() in _ORG_IDENTITIES:
        return True
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
        # A string field that IS the identity (author/creator values) is
        # always pseudonymized — including common-word handles the prose
        # passes below refuse to touch.
        stripped = text.strip()
        for handle, pseudo in self.map.items():
            if stripped in (handle, handle.split('@')[0]):
                return text.replace(stripped, pseudo)
        # Known handles/emails first (longest first to avoid partial hits),
        # then their local parts, then quoted-reply display names, then any
        # remaining non-bot email.
        for handle in sorted(self.map, key=len, reverse=True):
            # Full-handle replacement is boundary-guarded too: GitHub
            # logins are bare words (no '@'), and a short login like
            # 'sync' must not rewrite the inside of '(async storage'.
            if _prose_safe(handle):
                text = re.sub(
                    rf'\b{re.escape(handle)}\b', self.map[handle], text
                )
            local = handle.split('@')[0]
            if len(local) >= 4 and _prose_safe(local):
                # Word-boundary guarded: a short local part like 'glob' must
                # not rewrite the inside of words ('globally').
                text = re.sub(
                    rf'\b{re.escape(local)}\b', self.map[handle], text
                )
        text = self._scrub_mentions(text)
        text = _REPLY_NAME.sub(r'(In reply to comment #\1)', text)
        text = _SECRETS.sub('<secret-scrubbed>', text)
        text = mask_path_users(text)
        return _EMAIL.sub(
            lambda m: m.group(0) if _is_bot(m.group(0)) else '<email-scrubbed>',
            text,
        )

    def _scrub_mentions(self, text: str) -> str:
        """
        Pseudonymize @-mentions of identities that never authored a
        message (deleted accounts surface as author 'ghost', so CaseMap
        never maps their real handle — audit finding, deno_19766).

        Conservative: only handles that LOOK like personal accounts
        (contain an uppercase letter, digit, or hyphen) are mapped;
        lowercase-only tokens are left alone because @dev / @property /
        @media style technical tokens are indistinguishable from
        lowercase handles, and destroying technical content is worse
        than the residual risk (the sign-off review catches specifics).
        Scoped-package mentions (@scope/pkg) are skipped via the
        trailing-slash guard.
        """

        def _sub(m: re.Match) -> str:
            h = m.group(1)
            if h in self.map:
                return '@' + self.map[h]
            if _is_bot(h) or h.lower() in _COMMON_WORDS:
                return m.group(0)
            if not re.search(r'[A-Z0-9-]', h):
                return m.group(0)
            self.add(h)
            return '@' + self.map.get(h, h)

        return re.sub(r'@([A-Za-z0-9][A-Za-z0-9-]{2,38})\b(?!/)', _sub, text)

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
                # Cross-case application multiplies collision risk: a pool
                # case whose reporter is info@… must never rewrite the word
                # 'info' in every other graph.
                if len(token) >= 4 and _prose_safe(token):
                    rx = re.compile(rf'\b{re.escape(token)}\b')
                    n = len(rx.findall(text))
                    if n:
                        hits += n
                        text = rx.sub(pseudo, text)
    text = _SECRETS.sub('<secret-scrubbed>', text)
    text2 = mask_path_users(text)
    new = _EMAIL.sub(
        lambda mt: mt.group(0) if _is_bot(mt.group(0)) else '<email-scrubbed>',
        text2,
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
        if p.name.startswith(('bmo_', 'gh_', 'pg_')):
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
