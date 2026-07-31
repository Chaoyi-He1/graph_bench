from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from graph_bench.backbone.agent import Agent

_REGISTRY: dict[str, Callable[[dict], Agent]] = {}


def register_agent(name: str, factory: Callable[[dict], Agent]) -> None:
    _REGISTRY[name] = factory


def get_agent_factory(name: str) -> Callable[[dict], Agent]:
    if name not in _REGISTRY:
        msg = f'unknown agent {name!r}; registered: {sorted(_REGISTRY)}'
        raise KeyError(msg)
    return _REGISTRY[name]
