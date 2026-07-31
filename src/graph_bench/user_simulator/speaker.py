from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from graph_bench.oncall_graph.models import (
        Node,
        PersonaHint,
    )
    from graph_bench.user_simulator.models import (
        BaseResponse,
        SimulatorConfig,
        UserTurn,
    )


class _AnchorerProtocol(Protocol):
    """Structural type for a BM25 anchorer (duck-typed seam)."""

    def top_k(self, query: str, k: int) -> list[str]: ...


class _LlmProtocol(Protocol):
    """Structural type for an LLM client (duck-typed seam for Task 10)."""

    def invoke(self, input: Any) -> Any:  # noqa: ANN401, A002
        ...


# Directives whose payload is the verbatim deterministic user reply.
_PASSTHROUGH: frozenset[str] = frozenset(
    {'answer', 'symptoms', 'forced_reveal', 'opening'},
)

# Neutral follow-up that points ONLY at the agent's own words and adds
# no new information (anti-leakage: never names a tool/method).
_NEUTRAL_FOLLOWUP: str = '你说的具体怎么做？'  # noqa: RUF001

# Default 'nothing changed' reply for a failed solution attempt.
_NEUTRAL_NOCHANGE: str = '我试了，好像没什么变化。'  # noqa: RUF001

# Persona-appropriate satisfaction close.
_SATISFIED: str = '好像 OK 了，谢谢。'  # noqa: RUF001


class Speaker:
    """
    Stage 2 surface polish.

    Offline (``config.online`` False, or no online LLM wired) is
    fully deterministic: every reply is looked up from the directive
    and the ``BaseResponse`` payload, never invented. The render
    context is built through ``_build_context`` whose keys are a
    fixed allow-list, structurally guaranteeing the speaker cannot
    read the graph, sibling nodes, or any required_info/solution
    fields.

    The render pipeline is ``render`` -> ``_build_context`` ->
    dispatch to ``_render_offline`` (deterministic) or
    ``_render_online``. In this task ``_render_online`` is an
    offline-only stub; Task 9 wires the BM25 anchorer into it and
    Task 10 wires the real LLM call. The attribute names
    ``self._config`` / ``self._llm`` / ``self._anchorer`` are the
    cross-task contract.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        *,
        llm: _LlmProtocol | None = None,
        anchorer: _AnchorerProtocol | None = None,
        leak_context: dict | None = None,
    ) -> None:
        self._config = config
        self._llm = llm
        self._anchorer = anchorer
        # §13.5 experiment 1 only: non-None under leak_profile A/B.
        # Deliberately breaks the anti-leakage invariant to quantify
        # what that invariant is worth; None (profile C) in production.
        self._leak_context = leak_context

    def render(
        self,
        base: BaseResponse,
        *,
        node: Node,
        persona: PersonaHint | None,
        history: list[UserTurn],
    ) -> str:
        context = self._build_context(
            base,
            node=node,
            persona=persona,
            history=history,
        )
        body = (
            self._render_online(context)
            if self._config.online
            else self._render_offline(context)
        )
        if base.must_convey:
            return (
                f'{base.must_convey} {body}'.strip()
                if body
                else base.must_convey
            )
        return body

    def _render_offline(self, context: dict) -> str:
        directive = context['directive']
        payload = context['payload']
        if directive in _PASSTHROUGH:
            return payload if payload is not None else ''
        if directive == 'neutral_followup':
            return payload if payload else _NEUTRAL_FOLLOWUP
        if directive == 'neutral_nochange':
            return payload if payload else _NEUTRAL_NOCHANGE
        if directive == 'satisfied':
            return payload if payload else _SATISFIED
        return payload if payload is not None else ''

    def _render_online(self, context: dict) -> str:
        # Online persona polish. The offline render is the source of
        # truth (the deterministic draft + safe fallback); the LLM only
        # restyles it, never adds facts. Anti-leakage: only the persona
        # dict, this node's visible symptoms, and the draft enter the
        # prompt — never the graph, required_info, or canonical answers.
        import json  # noqa: PLC0415

        from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
            SPEAKER_PERSONA_PROMPT,
        )
        from graph_bench.user_simulator.provider import (  # noqa: PLC0415
            extract_text,
        )

        if self._llm is None:
            return self._render_offline(context)
        offline_text = self._render_offline(context)
        persona = context['persona']
        persona_text = (
            f'experience_level={persona.get("experience_level")}, '
            f'communication_style={persona.get("communication_style")}'
        )
        if context.get('intent'):
            from graph_bench.user_simulator.prompts import (  # noqa: PLC0415
                SPEAKER_REACT_PROMPT,
            )

            prompt = SPEAKER_REACT_PROMPT.format(
                persona=persona_text,
                symptoms=json.dumps(
                    context['symptoms_visible'], ensure_ascii=False
                ),
                history='\n'.join(f'- {h}' for h in context['history'])
                or '(none)',
                intent=context['intent'],
                draft=offline_text,
            )
        else:
            examples: list[str] = []
            if self._anchorer is not None and context['payload']:
                examples = self._anchorer.top_k(
                    context['payload'],
                    self._config.bm25_top_k,
                )
            prompt = SPEAKER_PERSONA_PROMPT.format(
                persona=persona_text,
                symptoms=json.dumps(
                    context['symptoms_visible'],
                    ensure_ascii=False,
                ),
                examples='\n'.join(f'- {e}' for e in examples) or '(none)',
                draft=offline_text,
            )
        if self._leak_context is not None:
            prompt += self._leak_suffix()
        try:
            polished = extract_text(self._llm.invoke(prompt)).strip()
        except (ValueError, TypeError, AttributeError):
            polished = ''
        return polished or offline_text

    def _leak_suffix(self) -> str:
        """§13.5 A/B experiment block appended to the online prompt."""
        leak = self._leak_context or {}
        parts = [
            f'\n\n[泄漏实验设置 {leak.get("profile")}]'
            ' 你其实完整经历过这次排障，下面是你额外知道的信息'  # noqa: RUF001
            '（仅实验用；正式评测不会提供）。'  # noqa: RUF001
            '你可以像看过全程的用户那样自然地利用这些知识：',  # noqa: RUF001
        ]
        conditions = leak.get('satisfaction_conditions') or []
        if conditions:
            parts.append('满足条件：')  # noqa: RUF001
            parts.extend(f'- {c}' for c in conditions)
        conversation = leak.get('original_conversation') or []
        if conversation:
            parts.append('原始对话：')  # noqa: RUF001
            parts.extend(f'- {line}' for line in conversation)
        return '\n'.join(parts)

    def _build_context(
        self,
        base: BaseResponse,
        *,
        node: Node,
        persona: PersonaHint | None,
        history: list[UserTurn],
    ) -> dict:
        # Anti-leakage allow-list: the ONLY fields the renderer may
        # read. No graph, no sibling nodes, no required_info,
        # required_elements_for_full_match, or satisfaction_conditions.
        return {
            'directive': base.directive,
            'payload': base.payload,
            'symptoms_visible': list(node.symptoms_visible),
            'info_state': list(node.info_state),
            'persona': {
                'experience_level': (
                    persona.experience_level if persona else None
                ),
                'communication_style': (
                    persona.communication_style if persona else None
                ),
            },
            'history': [turn.text for turn in history],
            'intent': base.intent,
        }
