from __future__ import annotations

import logging
import re
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# A CJK codepoint range (Unified Ideographs + common extensions) used
# to split Chinese characters individually while keeping ASCII words.
_CJK = r'一-鿿㐀-䶿豈-﫿'
# One CJK char, OR a run of ASCII alphanumerics (a "word").
_TOKEN_RE = re.compile(rf'[{_CJK}]|[a-zA-Z0-9]+')

_BM25_K1 = 1.5
_BM25_B = 0.75


def tokenize_cjk(text: str) -> list[str]:
    """
    Split CJK chars individually and ASCII words whole; lowercase.

    Punctuation and whitespace are dropped. Used for both corpus
    indexing and query tokenization so BM25 scoring is consistent.
    """
    if not text:
        return []
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


class Bm25Anchorer:
    """
    Self-contained BM25-Okapi over a small style corpus.

    Classic Okapi parameters (k1=1.5, b=0.75). Style-only retrieval:
    ``top_k`` returns the highest-scoring corpus strings verbatim so
    the online speaker can use them as few-shot voice examples. Never
    a content source.
    """

    def __init__(self, corpus: list[str]) -> None:
        import math  # noqa: PLC0415

        self._math = math
        self._corpus = list(corpus)
        self._docs = [tokenize_cjk(doc) for doc in self._corpus]
        self._doc_len = [len(d) for d in self._docs]
        n = len(self._docs)
        self._avgdl = (sum(self._doc_len) / n) if n else 0.0
        # Document frequency per term.
        self._df: dict[str, int] = {}
        for doc in self._docs:
            for term in set(doc):
                self._df[term] = self._df.get(term, 0) + 1
        # Smoothed IDF (BM25 form, floored at 0).
        self._idf: dict[str, float] = {}
        for term, df in self._df.items():
            self._idf[term] = max(
                0.0,
                math.log((n - df + 0.5) / (df + 0.5) + 1.0),
            )

    def _score(self, q_terms: list[str], doc_idx: int) -> float:
        doc = self._docs[doc_idx]
        if not doc:
            return 0.0
        # Term frequencies in this document.
        freqs: dict[str, int] = {}
        for term in doc:
            freqs[term] = freqs.get(term, 0) + 1
        dl = self._doc_len[doc_idx]
        score = 0.0
        for term in q_terms:
            tf = freqs.get(term, 0)
            if tf == 0:
                continue
            idf = self._idf.get(term, 0.0)
            denom = tf + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / self._avgdl)
            score += idf * (tf * (_BM25_K1 + 1.0)) / denom
        return score

    def top_k(self, query: str, k: int) -> list[str]:
        if not self._corpus or k <= 0:
            return []
        q_terms = tokenize_cjk(query)
        scored = [
            (self._score(q_terms, i), i) for i in range(len(self._corpus))
        ]
        # Highest score first; stable tie-break by original index.
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [self._corpus[i] for score, i in scored[:k] if score > 0.0]


def mine_user_corpus(
    testcases_dir: str | Path,
    exclude_task_id: str,
) -> list[str]:
    """
    Mine user-side utterances from every OTHER task's graph JSON.

    Collects only each clarification's
    ``user_answer_in_this_oncall`` across every ``*.json`` in
    ``testcases_dir`` whose ``task_id`` != ``exclude_task_id``. Issue
    bodies and solution text are deliberately excluded to avoid
    leaking content; this corpus is a style nudge only. The mined
    corpus size is logged at INFO as a §10 sanity check.
    """
    # Lazy: keep oncall_graph import out of module import time.
    from graph_bench.oncall_graph.models import (  # noqa: PLC0415
        Task,
    )

    directory = Path(testcases_dir)
    corpus: list[str] = []
    for json_path in sorted(directory.glob('*.json')):
        try:
            task = Task.model_validate_json(
                json_path.read_text(encoding='utf-8'),
            )
        except (ValueError, OSError):
            # Skip unparseable/unreadable files defensively.
            continue
        if task.task_id == exclude_task_id:
            continue
        for edge in task.graph.edges:
            for clar in edge.clarifications:
                answer = clar.user_answer_in_this_oncall
                if answer:
                    corpus.append(answer)
    _LOGGER.info(
        'mined user-style corpus: %d utterances from %s (excluding %s)',
        len(corpus),
        directory,
        exclude_task_id,
    )
    return corpus
