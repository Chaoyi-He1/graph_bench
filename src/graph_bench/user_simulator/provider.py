from __future__ import annotations

import os
from typing import Any

from graph_bench.llm import build_chat_client, resolve


def resolve_base_url() -> str:
    """
    Return the responses endpoint the simulator should call.

    ``SIM_RESPONSES_BASE_URL`` overrides the shared
    ``GRAPH_BENCH_LLM_BASE_URL`` so the simulator can be pinned to a
    different endpoint than other components when an experiment requires it.
    """
    return os.environ.get('SIM_RESPONSES_BASE_URL') or str(
        resolve('GRAPH_BENCH_LLM_BASE_URL')
    )


def get_llm():  # noqa: ANN201  (LangChain chat client; lazy import)
    """
    Build the user-simulator chat client.

    The model comes from ``SIM_MODEL`` (falling back to
    ``GRAPH_BENCH_LLM_MODEL``). Pin ``SIM_MODEL`` explicitly when running
    comparisons: the simulator drives both the simulated user and the
    turn->edge judge, so letting it drift silently makes runs incomparable.
    """
    return build_chat_client(
        model=os.environ.get('SIM_MODEL')
        or str(resolve('GRAPH_BENCH_LLM_MODEL')),
        base_url=resolve_base_url(),
        effort=os.environ.get('SIM_REASONING_EFFORT'),
    )


def extract_text(message) -> str:  # noqa: ANN001
    """
    Extract text from a LangChain ``BaseMessage``-like object.

    Handles both chat-completion string content and Responses-API list
    content (a list of ``{'type': 'text', 'text': ...}`` dicts, bare
    strings, and metadata dicts that are skipped).
    """
    content: Any = getattr(message, 'content', message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if (
                isinstance(item, dict)
                and item.get('type') == 'text'
                and 'text' in item
            ):
                parts.append(str(item['text']))
            elif isinstance(item, str):
                parts.append(item)
        return ''.join(parts)
    return ''
