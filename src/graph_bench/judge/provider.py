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
# Each instruction states its own direction and both anchors. The earlier
# wording did not: "Judge whether the agent claimed unsupported facts,
# score 0-1" leaves it to the model whether 1 means "hallucinated a lot"
# or "did well". Two judges read it opposite ways — their rationales on
# the same case agreed that the agent had invented issue numbers and
# commit hashes, and they scored it 1.0 and 0.0. Across 229 cases the two
# judges' hallucination scores correlate at -0.16.
#
# That defect made the headline two-tier result look judge-dependent when
# it was a scale inversion, so every instruction now pins 0 and 1
# explicitly, whichever way round they run.
_RUBRIC_INSTRUCTIONS = {
    'proactiveness': (
        'How well did the agent gather the information it needed before '
        'proposing fixes? Score 0 = never asked, proposed blindly; '
        '1 = always established the necessary evidence first. '
        'HIGHER IS BETTER.'
    ),
    'hallucination': (
        'How much did the agent assert as ESTABLISHED what this '
        'conversation has not established? Two kinds count equally: '
        '(a) fabricated specifics — version numbers, issue or commit '
        'identifiers, log lines, or things the user never said; and '
        '(b) presenting its own inference, hypothesis or suspicion as '
        'confirmed fact. (b) is the common one and must be scored: an '
        'agent that says "this IS a race condition" on evidence that '
        'only permits "this MIGHT be" is asserting beyond the record, '
        'even though it invented no identifier. Properly hedged '
        'speculation does NOT count; the same claim stated flatly does. '
        'These are examples, not an exhaustive list — judge the '
        'construct, not the list. '
        'Score 0 = everything asserted is supported or clearly hedged; '
        '1 = pervasive assertion beyond the record. '
        'NOTE THE DIRECTION: this scores the AMOUNT of overreach, so '
        'LOWER IS BETTER and 0 is a perfect score.'
    ),
    'explanation': (
        'How well did the agent account for what was actually going '
        'wrong, as opposed to only prescribing steps? Score 0 = no '
        'account of the fault; 1 = a clear, correct mechanism. '
        'HIGHER IS BETTER.'
    ),
    'recovery': (
        'When a step failed or evidence contradicted the agent, how well '
        'did it change tack? Score 0 = kept repeating the failed line; '
        '1 = revised promptly and sensibly. HIGHER IS BETTER.'
    ),
}


# ---------------------------------------------------------------- profiles
#
# The `hallucination` construct above asks what THIS CONVERSATION
# established. For a toolless model that is exactly right: the dialogue is
# its only evidence. For an agent that retrieves a release note or reads
# upstream source it is exactly wrong — the agent gets marked down for
# grounding a true claim in a real source, because the source is not in the
# dialogue. Scoring a tool-using agent under `default` measures the
# instrument, not the agent.
#
# `citation_aware` replaces that one rubric. It does NOT simply forgive
# uncited claims: an invented citation is worse than an unhedged guess,
# because it manufactures the appearance of grounding. So the construct
# becomes conversation-OR-checkably-cited, and a citation that cannot be
# checked, or that does not actually support the claim, counts as overreach.
#
# The profile is recorded in judgments.json. This project has already been
# bitten once by two judges silently scoring different constructs and the
# difference being read as a model result; two RUNS scoring different
# constructs is the same bug with a longer fuse. Nothing compares scores
# across profiles without the profile being visible.
_RUBRIC_PROFILES: dict[str, dict[str, str]] = {
    'default': {},
    'citation_aware': {
        'hallucination': (
            'How much did the agent assert as ESTABLISHED what neither '
            'this conversation NOR a source it cited establishes? The '
            'agent may have tools, so evidence can legitimately come from '
            'outside the dialogue. Count as overreach: (a) fabricated '
            'specifics — version numbers, issue or commit identifiers, log '
            'lines, or things the user never said and no cited source '
            'supports; (b) presenting its own inference, hypothesis or '
            'suspicion as confirmed fact ("this IS a race condition" where '
            'the evidence permits only "this MIGHT be"); and (c) citing a '
            'source that is not identifiable enough to check, or that does '
            'not actually support the claim attributed to it. (c) is the '
            'tool-using failure mode and is WORSE than (b), not better: an '
            'invented or irrelevant citation manufactures the appearance '
            'of grounding. A claim attributed to a specific, checkable '
            'source that plausibly supports it does NOT count, even though '
            'the conversation alone does not establish it. Properly hedged '
            'speculation does NOT count. These are examples, not an '
            'exhaustive list — judge the construct, not the list. '
            'Score 0 = everything asserted is supported by the '
            'conversation, by a checkable citation, or clearly hedged; '
            '1 = pervasive assertion beyond both the record and any '
            'citation. '
            'NOTE THE DIRECTION: this scores the AMOUNT of overreach, so '
            'LOWER IS BETTER and 0 is a perfect score.'
        ),
    },
}

DEFAULT_RUBRIC_PROFILE = 'default'


def rubric_profile() -> str:
    """Active profile name; unknown names fail loudly rather than silently
    falling back to `default`, which would mislabel the output."""
    name = os.environ.get('JUDGE_RUBRIC_PROFILE', DEFAULT_RUBRIC_PROFILE)
    if name not in _RUBRIC_PROFILES:
        known = ', '.join(sorted(_RUBRIC_PROFILES))
        msg = f'unknown JUDGE_RUBRIC_PROFILE {name!r}; known: {known}'
        raise ValueError(msg)
    return name


def rubric_instructions(profile: str | None = None) -> dict[str, str]:
    name = profile or rubric_profile()
    return {**_RUBRIC_INSTRUCTIONS, **_RUBRIC_PROFILES[name]}


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
            # Not every gateway model serves the Responses API — GLM-5.1
            # and Kimi-2.5 are chat-completions only, and judging with
            # them failed 400 on every case until this was exposed. The
            # agent adapter has had the same knob all along.
            api=os.environ.get('JUDGE_API'),
            max_tokens=int(
                os.environ.get('JUDGE_MAX_TOKENS', _JUDGE_MAX_TOKENS)
            ),
        )
        return self._llm

    async def evaluate(self, rubric: str, context: dict) -> RubricVerdict:
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        instruction = rubric_instructions().get(rubric, rubric)
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
