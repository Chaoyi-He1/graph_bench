"""
Reference system-under-test agent: any OpenAI-compatible Responses endpoint.

Stateless per call — the backbone hands the full leak-free transcript every
turn, so the conversation is reconstructed as one message list. Configure via
``agent_config`` (``model``, ``base_url``, ``api_key_env``, ``effort``,
``system_prompt``) with ``GRAPH_BENCH_LLM_*`` env fallbacks.

This adapter deliberately has no tools and no repository access: it measures
what a plain conversational model does inside the benchmark loop, and doubles
as the wiring example for adapters around real products.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

from graph_bench.recorder.models import AgentTelemetry, TokenUsage

if TYPE_CHECKING:
    from graph_bench.backbone.models import AgentTurn, RecoveryMode

# Output budget per turn. Must leave room for the answer AFTER the
# model's reasoning tokens; the gateway's own default (1000) does not.
_DEFAULT_MAX_TOKENS = 8000

_DEFAULT_SYSTEM_PROMPT = (
    'You are a senior support engineer helping a user diagnose and fix a '
    'software problem over chat. The user executes actions; you cannot run '
    'anything yourself. Ask for the specific evidence you need, propose '
    'concrete steps one at a time, ground your conclusions in what the user '
    'actually reported, and reply in the language the user writes in.'
)


def _with_images(text: str, paths: list[str]) -> list[dict]:
    """A multimodal user message: the text plus each screenshot inline.

    Images are read from disk and base64'd rather than linked — the
    corpus ships them alongside the graphs, and a gateway cannot fetch a
    local path.
    """
    import base64  # noqa: PLC0415
    import mimetypes  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    parts: list[dict] = [{'type': 'text', 'text': text}]
    for path in paths:
        file = Path(path)
        if not file.exists():
            continue
        mime = mimetypes.guess_type(file.name)[0] or 'image/png'
        data = base64.b64encode(file.read_bytes()).decode()
        parts.append({
            'type': 'image_url',
            'image_url': {'url': f'data:{mime};base64,{data}'},
        })
    return parts


class APIChatAgent:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._llm = None
        self._system_prompt = cfg.get('system_prompt', _DEFAULT_SYSTEM_PROMPT)

    def _client(self):  # noqa: ANN202
        if self._llm is not None:
            return self._llm
        from graph_bench.llm import build_chat_client  # noqa: PLC0415

        key_env = self._cfg.get('api_key_env')
        # An explicit output budget is REQUIRED, not a tuning knob. Left
        # unset, the gateway caps output at 1000 tokens; a reasoning model
        # spends that on reasoning and returns an empty message, which the
        # benchmark then scores as a bad turn. That silently turned one
        # matrix row into 76% empty replies before it was caught.
        self._llm = build_chat_client(
            model=self._cfg.get('model'),
            base_url=self._cfg.get('base_url'),
            api_key=os.environ.get(key_env) if key_env else None,
            effort=self._cfg.get('effort'),
            api=self._cfg.get('api'),
            max_tokens=int(self._cfg.get('max_tokens', _DEFAULT_MAX_TOKENS)),
        )
        return self._llm

    async def respond(
        self, turn: AgentTurn, *, mode: RecoveryMode = 'normal'
    ) -> AgentTelemetry:
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        messages: list = [('system', self._system_prompt)]
        for msg in turn.transcript:
            role = 'user' if msg.role == 'user' else 'assistant'
            messages.append((role, msg.text))
        if not turn.transcript or turn.transcript[-1].role != 'user':
            messages.append(('user', turn.latest_user_text))
        # The reporter's screenshots reach this adapter on the turn and,
        # until this was added, went straight in the bin: the corpus hooks
        # 62 cases' images to the exact state or question they evidence,
        # and the agent never saw one. That silently made the no-images
        # ablation a null result by construction — removing evidence
        # nobody consumed changed nothing (-0.0002 on 48 paired cases).
        #
        # Off by default: attaching images changes what every row is
        # answering, so it must not land mid-table.
        if self._cfg.get('multimodal') and turn.latest_user_images:
            messages[-1] = ('user', _with_images(
                messages[-1][1], turn.latest_user_images
            ))

        start = time.monotonic()
        reply = await self._client().ainvoke(messages)
        latency_ms = (time.monotonic() - start) * 1000
        usage = getattr(reply, 'usage_metadata', None) or {}
        return AgentTelemetry(
            text=extract_text(reply),
            model=self._cfg.get('model')
            or os.environ.get('GRAPH_BENCH_LLM_MODEL'),
            usage=TokenUsage(
                prompt_tokens=usage.get('input_tokens'),
                completion_tokens=usage.get('output_tokens'),
            )
            if usage
            else None,
            latency_ms=latency_ms,
        )

    async def aclose(self) -> None:
        return None


from graph_bench.backbone.registry import register_agent


def _api_factory(cfg: dict) -> APIChatAgent:
    return APIChatAgent(cfg)


register_agent('api', _api_factory)
