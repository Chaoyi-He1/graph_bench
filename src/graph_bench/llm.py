"""
Shared LLM client builder for graph_bench.

Every LLM consumer in this repository — user simulator, judge, pipeline
scripts, the reference API agent — goes through :func:`build_chat_client`,
which targets any OpenAI-compatible **Responses API** endpoint. Configuration
comes from environment variables so no credentials or gateway URLs ever live
in the repository:

- ``GRAPH_BENCH_LLM_BASE_URL``  endpoint base, e.g. ``https://host/api/v1``
  (the client POSTs to ``{base}/responses``)
- ``GRAPH_BENCH_LLM_API_KEY``   bearer key
- ``GRAPH_BENCH_LLM_MODEL``     model/catalog id to request
- ``GRAPH_BENCH_LLM_EFFORT``    optional reasoning effort (low/medium/high)

Role-specific overrides (``SIM_RESPONSES_BASE_URL``, ``SIM_MODEL``,
``JUDGE_RESPONSES_BASE_URL``, ``JUDGE_MODEL``, ``JUDGE_REASONING_EFFORT``)
take precedence in their corresponding modules so simulator and judge can be
pinned independently when comparability requires it.
"""

from __future__ import annotations

import os


class MissingLLMConfigError(RuntimeError):
    def __init__(self, var: str) -> None:
        super().__init__(
            f'{var} is not set. graph_bench talks to an OpenAI-compatible '
            f'Responses API endpoint configured entirely via environment '
            f'variables: GRAPH_BENCH_LLM_BASE_URL, GRAPH_BENCH_LLM_API_KEY, '
            f'GRAPH_BENCH_LLM_MODEL (optional GRAPH_BENCH_LLM_EFFORT).'
        )


def resolve(name: str, *fallbacks: str, required: bool = True) -> str | None:
    for var in (name, *fallbacks):
        value = os.environ.get(var)
        if value:
            return value
    if required:
        raise MissingLLMConfigError(name if not fallbacks else fallbacks[-1])
    return None


def _identity_headers() -> dict[str, str]:
    """End-user identity headers some gateways require on every call.

    ``GRAPH_BENCH_USER_NAME`` / ``GRAPH_BENCH_USER_EMAIL`` (falling back to
    ``USER``/``GIT_AUTHOR_*``) are forwarded as ``x-user-name`` /
    ``x-user-email``. Both are optional: a plain OpenAI endpoint ignores
    them, and nothing here is committed to the repository.
    """
    name = os.environ.get('GRAPH_BENCH_USER_NAME') or os.environ.get(
        'GIT_AUTHOR_NAME'
    )
    email = os.environ.get('GRAPH_BENCH_USER_EMAIL') or os.environ.get(
        'GIT_AUTHOR_EMAIL'
    )
    headers: dict[str, str] = {}
    if name:
        headers['x-user-name'] = name
    if email:
        headers['x-user-email'] = email
    return headers


def build_chat_client(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    effort: str | None = None,
    max_tokens: int | None = None,
    api: str | None = None,
):  # noqa: ANN201  (LangChain chat client; lazy import)
    """Build a LangChain ``ChatOpenAI`` bound to the configured endpoint.

    ``api`` selects the wire protocol: ``'responses'`` (default) or
    ``'chat'`` for endpoints that only serve /chat/completions — several
    non-OpenAI models behind an OpenAI-compatible gateway reject the
    Responses API, and reasoning-effort is meaningless for them.

    Returned objects expose ``invoke``/``ainvoke`` and are consumed through
    ``graph_bench.user_simulator.provider.extract_text``.
    """
    from langchain_openai import ChatOpenAI  # noqa: PLC0415

    api = api or os.environ.get('GRAPH_BENCH_LLM_API') or 'responses'
    kwargs: dict = {
        'base_url': base_url or resolve('GRAPH_BENCH_LLM_BASE_URL'),
        'api_key': api_key or resolve('GRAPH_BENCH_LLM_API_KEY'),
        'model': model or resolve('GRAPH_BENCH_LLM_MODEL'),
        'use_responses_api': api == 'responses',
    }
    headers = _identity_headers()
    if headers:
        kwargs['default_headers'] = headers
    # A hung upstream must not pin a worker forever: the gateway returns
    # intermittent 502/ReadTimeout under load, and without an explicit
    # timeout a stuck call blocks its slot indefinitely. Both knobs are
    # env-overridable for slow local endpoints.
    kwargs['timeout'] = float(os.environ.get('GRAPH_BENCH_LLM_TIMEOUT', 420))
    kwargs['max_retries'] = int(os.environ.get('GRAPH_BENCH_LLM_RETRIES', 3))
    effort = effort or os.environ.get('GRAPH_BENCH_LLM_EFFORT')
    if effort and api == 'responses':
        kwargs['reasoning'] = {'effort': effort}
    if max_tokens:
        kwargs['max_tokens'] = max_tokens
    return ChatOpenAI(**kwargs)
