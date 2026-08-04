"""Release sign-off reviews via the gateway model (GPT-5.6 class).

Reads a pending-case list (slug/graph/raw/review paths), builds one review
prompt per case (review page + graph JSON + the same capped thread render
the drafting stage saw), asks for a strict-JSON verdict, and writes one
JSON per case under runs/signoff_gpt56/. Skips cases whose result file
already exists (idempotent resume).

Usage: uv run --native-tls python scripts/signoff_gpt56.py runs/signoff_pending_gpt56.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))


def _load_env(path: Path) -> None:
    import os  # noqa: PLC0415

    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())


_load_env(REPO / '.env')

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.pipeline.draft import render_thread  # noqa: E402
from graph_bench.user_simulator.provider import extract_text  # noqa: E402

OUT = REPO / 'runs' / 'signoff_gpt56'
OUT.mkdir(parents=True, exist_ok=True)

PROMPT = """You are the RELEASE SIGN-OFF reviewer for one benchmark task \
graph. Your verdict decides corpus membership.

The graph is an ANSWER KEY for a leak-safe multi-turn diagnostic benchmark: \
nodes = (system_state, info_state); clarification answers are the user's RAW \
output at that time (engineer conclusions belong in \
info_inferred_by_engineer/inference_hint); is_known_blind_path marks \
thread-falsified attempts; a simulator speaks ONLY node symptoms, \
volunteered_info and authored answers; scoring fields are \
required_elements_for_full_match, approach_keywords, satisfaction_conditions.

CHECK, evidence-first (quote thread+graph for every finding; try to REFUTE \
each candidate before filing):
a. Faithfulness: build a who-knew-what-when timeline from the thread; every \
answer/symptom must be evidenced and timed correctly (no future knowledge in \
any user-speakable channel; measurement answers raw-output-only; no \
retracted hypothesis scored as root cause; no invented mechanisms for \
link-only fixes).
b. Leak safety: no clarification question names fix contents or downstream \
solution vocabulary; blind paths only for thread-falsified attempts; \
verification-timing rule respected (retests of builds containing the landed \
fix belong terminal-side).
c. Scoring sanity: required_info ids obtainable on-path; no post-snapshot \
PR/version literals in scoring fields; satisfaction_conditions demand only \
facts the graph surfaces.
d. Voice/persona: first-person answers; multi-user folds disclosed in edge \
comments and persona-compatible.
e. Prior findings listed on the review page: verify each listed repair \
actually landed in the graph.

SIGN RULE: sign=true ONLY if no high-severity finding AND no unrepaired \
medium-severity finding. Low findings do not block signing (file them \
anyway).

Return ONLY one JSON object, no fences, no prose:
{{"verdict": "clean"|"minor_issues"|"needs_rework", "sign": true|false,
"summary": "<1-3 sentences>",
"findings": [{{"severity": "high"|"medium"|"low", "class": "<short>",
"location": "<node/edge/field>", "claim": "<1-2 sentences>"}}]}}

=== REVIEW PAGE (checklist + prior findings) ===
{review}

=== TASK GRAPH (JSON) ===
{graph}

=== SOURCE THREAD (scrubbed; same capped render the drafting stage saw) ===
{thread}
"""


async def review_one(llm, c: dict, sem: asyncio.Semaphore) -> None:
    out = OUT / f'{c["slug"]}.json'
    if out.exists():
        print(f'{c["slug"]}: exists, skip')
        return
    async with sem:
        review = (REPO / c['review']).read_text() if (REPO / c['review']).exists() else '(no review page)'
        graph = (REPO / c['graph']).read_text()
        thread = render_thread(json.loads((REPO / c['raw']).read_text()))
        prompt = PROMPT.format(review=review[:30000], graph=graph, thread=thread)
        try:
            raw = extract_text(await llm.ainvoke(prompt))
            start, end = raw.find('{'), raw.rfind('}')
            data = json.loads(raw[start : end + 1])
            data['slug'] = c['slug']
            data['model'] = 'gpt56'
            out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
            print(
                f'{c["slug"]}: {data.get("verdict")} sign={data.get("sign")} '
                f'findings={len(data.get("findings") or [])}'
            )
        except Exception as exc:  # noqa: BLE001 — keep batch going
            print(f'{c["slug"]}: FAILED {str(exc)[:120]}')


async def main() -> None:
    cases = json.loads(Path(sys.argv[1]).read_text())
    llm = build_chat_client(effort='high', max_tokens=8000)
    sem = asyncio.Semaphore(4)
    await asyncio.gather(*(review_one(llm, c, sem) for c in cases))
    done = len(list(OUT.glob('*.json')))
    print(f'\ngpt56 sign-off: {done} results in {OUT}')


if __name__ == '__main__':
    asyncio.run(main())
