from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from graph_bench.judge.models import RubricVerdict

# The judge writes a score AND a rationale naming the turns it relies on,
# which is the longest output anything in this harness produces. Left
# unset, the gateway caps it at 1000 tokens: a reasoning model spends most
# of that thinking, the JSON truncates mid-string, and the parse fails.
# That failure used to become score 0.0 — free full marks on the one
# rubric the grade inverts (1 - hallucination) and a zero on the other
# three. 208 of 229 cases in the first main-table row were scored that
# way before this was caught.
_JUDGE_MAX_TOKENS = 8000

if TYPE_CHECKING:
    from graph_bench.judge.models import JudgeConfig

# Exact rubric prompts are locked at implementation against design-doc
# §9.3; this skeleton calls the shared LLM with a JSON instruction and
# parses a RubricVerdict. Online-only; CI uses StubBackend.
_RUBRIC_INSTRUCTIONS = {
    'proactiveness': 'Judge whether the agent proactively gathered info.',
    'hallucination': 'Judge whether the agent claimed unsupported facts.',
    'explanation': 'Judge the clarity of the agent explanations.',
    'recovery': 'Judge whether the agent recovered from a wrong path.',
}


def _extract_json(raw: str) -> dict | None:
    """
    The JSON object in a judge reply, however it was wrapped.

    Models fence their output (```json ... ```), preface it, or trail a
    closing remark. Requiring the whole reply to parse threw all of that
    away.
    """
    text = raw.strip()
    if not text:
        return None
    if text.startswith('```'):
        text = text.split('```')[1] if '```' in text[3:] else text[3:]
        text = text.removeprefix('json').strip()
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) and 'score' in data else None


class LLMBackend:
    """Real provider-backed judge. Online only (needs endpoint env vars).

    ``JudgeConfig.model`` selects the judge model (falling back to
    ``JUDGE_MODEL`` / ``GRAPH_BENCH_LLM_MODEL``); ``JUDGE_RESPONSES_BASE_URL``
    and ``JUDGE_REASONING_EFFORT`` override endpoint/effort so the judge can
    be pinned independently of the simulator.
    """

    def __init__(self, config: JudgeConfig) -> None:
        self._config = config
        self._llm = None

    def _client(self):  # noqa: ANN202
        if self._llm is not None:
            return self._llm
        from graph_bench.llm import build_chat_client, resolve  # noqa: PLC0415

        model = (
            self._config.model
            or os.environ.get('JUDGE_MODEL')
            or str(resolve('GRAPH_BENCH_LLM_MODEL'))
        )
        self._llm = build_chat_client(
            model=model,
            base_url=os.environ.get('JUDGE_RESPONSES_BASE_URL')
            or str(resolve('GRAPH_BENCH_LLM_BASE_URL')),
            effort=os.environ.get('JUDGE_REASONING_EFFORT'),
            max_tokens=int(
                os.environ.get('JUDGE_MAX_TOKENS', _JUDGE_MAX_TOKENS)
            ),
        )
        return self._llm

    async def evaluate(self, rubric: str, context: dict) -> RubricVerdict:
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        instruction = _RUBRIC_INSTRUCTIONS.get(rubric, rubric)
        prompt = (
            f'{instruction}\n\nReturn JSON with keys score (0-1), '
            f'rationale, evidence_turn_indices (list[int]).\n\n'
            f'Transcript: {context.get("transcript")}\n'
            f'Agent reasoning: {context.get("reasoning")}'
        )
        raw = extract_text(await self._client().ainvoke(prompt))
        data = _extract_json(raw)
        if data is None:
            # Never fabricate a score from a failed parse. Raising sends the
            # case back through the judge's retry, and anything that still
            # fails is left unjudged where run_integrity.py reports it —
            # visibly absent beats silently wrong.
            raise ValueError(
                f'{rubric}: unparseable judge reply ({len(raw)} chars): '
                f'{raw[:160]!r}'
            )
        return RubricVerdict.model_validate(data)

    async def resolve_tier(self, context: dict) -> str:
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        prompt = (
            'Does the agent DISPLAY inference about the skipped info — '
            'in its reply to the user (primary evidence, per §8.8) or '
            'in its private reasoning? Answer exactly inferred_shortcut '
            'or blind_shortcut.\n\n'
            f'Agent reply: {context.get("reply")}\n'
            f'Reasoning: {context.get("reasoning")}\n'
            f'Skipped: {context.get("shortcut_skipped_info")}\n'
            f'Hint: {context.get("inference_hint")}'
        )
        out = extract_text(await self._client().ainvoke(prompt)).strip()
        return 'inferred_shortcut' if 'inferred' in out else 'blind_shortcut'
