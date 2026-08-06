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
_ORG_IDENTITIES = {
    'mozilla', 'firefox', 'bugzilla', 'github', 'postgresql',
    # Org/product accounts that also appear inside URLs, package names and
    # prose; mapping them corrupts technical content
    # (github.com/home-assistant/core -> github.com/participantN/core).
    'home-assistant', 'react-native', 'react', 'native', 'expo', 'google',
    'aws', 'microsoft', 'apple', 'nvidia', 'docker', 'moby', 'containerd',
    'kubernetes', 'nodejs', 'denoland', 'duckdb', 'clickhouse', 'traefik',
    'micropython', 'flutter', 'ollama', 'vllm', 'pytorch', 'curl', 'caddy',
    'etcd', 'python', 'typescript', 'javascript', 'config', 'testing',
    'ghost',
}

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


# English function words: an @-mention of one ("@This is the fix") is
# markdown noise, never an account. Capitalization does not make a word
# account-shaped, which the mention pass previously assumed.
_STOPWORDS = {
    'this', 'that', 'these', 'those', 'the', 'and', 'but', 'for', 'not',
    'you', 'your', 'yours', 'our', 'ours', 'they', 'them', 'their', 'its',
    'here', 'there', 'when', 'where', 'while', 'with', 'without', 'from',
    'into', 'over', 'under', 'after', 'before', 'again', 'also', 'just',
    'only', 'same', 'each', 'both', 'other', 'another', 'some', 'any',
    'all', 'none', 'yes', 'no', 'ok', 'okay', 'thanks', 'thank', 'please',
    'hi', 'hey', 'hello', 'edit', 'note', 'fixed', 'closed', 'done',
}


# @-tokens that are technical, not people: npm scopes, decorators,
# annotations, doc tags. Anything else after an '@' on an issue tracker is
# treated as a handle.
_TECH_AT_TOKENS = {
    'types', 'babel', 'angular', 'vue', 'nestjs', 'nuxt', 'storybook',
    'testing-library', 'typescript-eslint', 'eslint', 'jest', 'swc',
    'rollup', 'vitejs', 'emotion', 'mui', 'radix-ui', 'tanstack',
    'expo-google-fonts', 'react-navigation', 'react-native-community',
    'react-native-async-storage', 'react-native-firebase', 'aws-sdk',
    'azure', 'google-cloud', 'grpc', 'kubernetes', 'octokit', 'sentry',
    'sinclair', 'std', 'core', 'lib', 'dev', 'next', 'latest', 'beta',
    'alpha', 'rc', 'stable', 'canary', 'nightly', 'main', 'master',
    'param', 'return', 'returns', 'throws', 'deprecated', 'override',
    'property', 'media', 'import', 'charset', 'keyframes', 'supports',
    'apply', 'tailwind', 'layer', 'font-face', 'entry', 'nogc', 'safe',
    'nonnull', 'nullable', 'suppress', 'link', 'see', 'since', 'author',
    'todo', 'fixme', 'xxx', 'sha', 'ref', 'head', 'entry',
}

# Private/lab hostnames leak organizational identity. Public code-hosting
# and package registries stay intact (they are provenance, not PII).
_PUBLIC_HOST_SUFFIXES = (
    'github.com', 'github.io', 'githubusercontent.com', 'gitlab.com',
    'bitbucket.org', 'stackoverflow.com', 'npmjs.com', 'pypi.org',
    'crates.io', 'golang.org', 'python.org', 'mozilla.org', 'postgresql.org',
    'kernel.org', 'debian.org', 'ubuntu.com', 'redhat.com', 'apache.org',
    'docker.com', 'docker.io', 'microsoft.com', 'apple.com', 'google.com',
    'googleapis.com', 'cloudflare.com', 'amazonaws.com', 'nvidia.com',
    'llvm.org', 'gnu.org', 'freedesktop.org', 'w3.org', 'ietf.org',
    'wikipedia.org', 'readthedocs.io', 'rust-lang.org', 'nodejs.org',
    'deno.land', 'huggingface.co', 'localhost', 'example.com',
)
_HOSTNAME = re.compile(
    r'\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'
    r'(?:com|org|net|edu|gov|io|dev|ai|co|us|uk|de|fr|cn|jp|ru|local|lan|'
    r'internal|intranet|corp)\b'
)


# Review/commit metadata carries identities that are not author fields:
# hg/git commit lines ("Author: Real Name <mail>"), Mozilla IRC nicks
# (":sdetar"), and review flags ("r=iain", "r?iain!", "a=RyanVM").
_COMMIT_AUTHOR = re.compile(
    r'(?im)^(\s*(?:Author|Committer|Reviewed-by|Signed-off-by|Acked-by|'
    r'Reported-by|Tested-by|Co-authored-by)\s*:\s*).+$'
)
_IRC_NICK = re.compile(r'(?<![A-Za-z0-9:])::?([a-z][a-z0-9_.-]{2,20})\b')
# Only Mozilla review-flag letters, and only with a name-shaped value:
# 'f=ma' / 'n=2' in prose or code must not be rewritten.
_REVIEW_FLAG = re.compile(
    r'(?<![A-Za-z0-9])(r|a|sr|ui-r)([=?])'
    r'([A-Za-z][A-Za-z0-9_.-]{2,20})([!+-]?)'
)


def mask_review_metadata(text: str) -> str:
    """Pseudonymize identity forms specific to review/commit metadata."""
    text = _COMMIT_AUTHOR.sub(r'\1<redacted-name>', text)
    text = _REVIEW_FLAG.sub(
        lambda m: f'{m.group(1)}{m.group(2)}<reviewer>{m.group(4)}', text
    )
    return _IRC_NICK.sub(':<nick>', text)


def mask_private_hosts(text: str) -> str:
    """Replace non-public FQDNs with <redacted-host>."""

    def _sub(m: re.Match) -> str:
        host = m.group(0)
        low = host.lower()
        if any(low == s or low.endswith('.' + s) for s in _PUBLIC_HOST_SUFFIXES):
            return host
        # Bare two-label domains are usually products/projects, not hosts;
        # organizational leakage lives in deeper names (host.dept.org.edu).
        if low.count('.') < 2:
            return host
        return '<redacted-host>'

    return _HOSTNAME.sub(_sub, text)


def _re_search_upper_digit(token: str) -> bool:
    return re.search(r'[A-Z0-9]', token) is not None


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


_PSEUDO = re.compile(r'^(reporter|participant\d+)$')


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
        # Reviewer-filed non-identity PII strings (see _EXTRA_IDENTITIES).
        self.redactions: list[str] = []

    def add(self, handle: str) -> None:
        # Idempotence: an already-scrubbed corpus re-scrubs to itself.
        # Without this, author fields that are ALREADY pseudonyms get
        # re-assigned by traversal order and every re-scrub renumbers
        # people (participant1 -> participant2 -> ...).
        if _PSEUDO.match(handle or ''):
            self.map.setdefault(handle, handle)
            return
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
            # Underscore counts as a boundary in RAW text so handles
            # embedded in filenames (…_hawkfish.csv) are caught; the graph
            # pass keeps \b to avoid rewriting snake_case info ids.
            if _prose_safe(handle):
                text = re.sub(
                    rf'(?<![A-Za-z0-9]){re.escape(handle)}(?![A-Za-z0-9])',
                    self.map[handle],
                    text,
                )
            local = handle.split('@')[0]
            if len(local) >= 4 and _prose_safe(local):
                # Boundary-guarded: a short local part like 'glob' must
                # not rewrite the inside of words ('globally').
                text = re.sub(
                    rf'(?<![A-Za-z0-9]){re.escape(local)}(?![A-Za-z0-9])',
                    self.map[handle],
                    text,
                )
        for secret in self.redactions:
            text = text.replace(secret, '<redacted>')
        text = self._scrub_mentions(text)
        text = _REPLY_NAME.sub(r'(In reply to comment #\1)', text)
        text = _SECRETS.sub('<secret-scrubbed>', text)
        text = mask_path_users(text)
        text = mask_private_hosts(text)
        text = mask_review_metadata(text)
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
            # Never re-map an existing pseudonym: a re-scrub would cascade
            # (@participant5 -> participant6 -> ...), destroying stability.
            if _PSEUDO.match(h):
                return m.group(0)
            if _is_bot(h) or h.lower() in _COMMON_WORDS | _STOPWORDS:
                return m.group(0)
            # On issue trackers an @-mention IS a handle by construction,
            # and most real handles are all-lowercase (@apolcyn, @bash).
            # Only technical @-tokens are exempt: npm scopes/orgs, decorator
            # and annotation names. Cross-case poisoning is no longer a risk
            # (a graph is scrubbed with its own map only), so the pass can
            # be aggressive here — a missed handle is a privacy defect,
            # while a false positive costs one rewritten technical token.
            if h.lower() in _TECH_AT_TOKENS or h.endswith('-'):
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


# Display names and signatures ("Best wishes, Yuri") never appear in author
# fields, so the automatic map misses them. Reviewers file them per case in
# a PRIVATE side file mapping slug -> {name: 'reporter'|'participant'}.
_EXTRA_IDENTITIES = (
    Path.home() / 'graph_bench_private' / 'extra_identities.json'
)


def scrub_raw(path: Path, apply: bool) -> dict:  # noqa: FBT001
    d = json.loads(path.read_text())
    reporter = (
        d['meta']['creator'] if 'meta' in d else d['reporter']
    )
    cm = CaseMap(reporter)
    _collect_handles(
        d, ('creator', 'author', 'attacher', 'setter', 'reporter'), cm
    )
    redactions: list[str] = []
    if _EXTRA_IDENTITIES.exists():
        extras = json.loads(_EXTRA_IDENTITIES.read_text()).get(path.stem, {})
        for name, role in extras.items():
            if role == 'reporter':
                cm.map.setdefault(name, 'reporter')
            elif role == 'redact':
                # Non-identity PII (private hostnames, internal URLs).
                redactions.append(name)
            elif role.startswith('alias:'):
                # A display name for someone who ALSO posts under a handle
                # ("Rob Murray" quoted in mail, robmry in the author field):
                # both must resolve to the SAME pseudonym, else one person
                # appears as two participants.
                handle = role.split(':', 1)[1]
                cm.map[name] = cm.map.get(handle) or cm.map.setdefault(
                    handle, f'participant{len(cm.map)}'
                )
            else:
                cm.add(name)
    cm.redactions = redactions
    scrubbed = cm.scrub_obj(d)
    if apply:
        path.write_text(
            json.dumps(scrubbed, ensure_ascii=False, indent=1) + '\n'
        )
    return cm.map




def scrub_graph(path: Path, maps: dict[str, dict], apply: bool) -> int:  # noqa: FBT001
    """Apply THIS CASE's handle map to its graph free text; count hits.

    Only the case's own map is applied. Cross-case application caused
    every identity-map defect this corpus has suffered: one case's
    handle ('info@…', an npm org, an @-mention of the word 'This')
    rewrote technical prose in 78 unrelated graphs. A graph can only
    legitimately mention identities from its own thread.
    """
    text = path.read_text()
    hits = 0
    own = maps.get(path.name)
    for m in ([own] if own else []):
        for handle, pseudo in m.items():
            for token in {handle, handle.split('@')[0]}:
                if token == pseudo or _PSEUDO.match(token):
                    continue  # identity/no-op from an already-scrubbed map
                # Cross-case application multiplies collision risk: a pool
                # case whose reporter is info@… must never rewrite the word
                # 'info' in every other graph. Beyond the common-word list,
                # ambiguous shapes are excluded outright: a cross-case token
                # must carry an uppercase letter or digit, or be a long
                # (>=8) pure word — short lowercase tokens ('config',
                # 'native') are indistinguishable from prose/technical text.
                # Cross-case tokens must be unmistakably account-shaped:
                # an uppercase letter or a digit. Lowercase-only handles
                # are still pseudonymized inside their OWN case (where the
                # author field proves they are identities); applying them
                # to 68 other graphs is what poisons technical text.
                distinctive = _re_search_upper_digit(token)
                if (
                    len(token) >= 4
                    and _prose_safe(token)
                    and distinctive
                    and not token.endswith(('-', '_'))
                ):
                    rx = re.compile(rf'\b{re.escape(token)}\b')
                    n = len(rx.findall(text))
                    if n:
                        hits += n
                        text = rx.sub(pseudo, text)
    text = _SECRETS.sub('<secret-scrubbed>', text)
    text2 = mask_review_metadata(mask_private_hosts(mask_path_users(text)))
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
