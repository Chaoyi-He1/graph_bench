"""
System-under-test adapter for an external CLI agent.

The point of this adapter is that the benchmark's execution-free property
belongs to the SCORING, not to the agent. Whether the system being measured
searches, retrieves, opens a sandbox or runs an experiment of its own is
part of its capability, and the harness should neither grant nor withhold
it. ``api.py`` measures a toolless model; this measures whatever the
configured command does, and a model is plugged in by naming it in the
command template.

Contract: the command is invoked once per turn and is expected to restore
its own session from ``{session}`` -- the same shape production agent
gateways use, and more robust than a long-lived pipe, since a crashed turn
does not lose the case.

Config (``agent_config``)::

    command          argv template, e.g.
                     ["myagent", "exec", "--model", "{model}",
                      "--session", "{session}", "--cd", "{workspace}"]
    model            substituted into {model}; also recorded as telemetry
    workspace_root   substituted into {workspace} (per-task subdirectory)
    send             "latest" (default, session-ful agent) | "transcript"
    prompt_arg       when set, the prompt is substituted into {prompt};
                     otherwise it is written to the process's stdin
    image_arg        argv template repeated per attached image, e.g.
                     ["--image", "{path}"]
    turn_timeout_s   per-turn wall clock (default 600)
    env              extra environment variables

Placeholders are substituted into argv ELEMENTS -- the command is never
handed to a shell, so prompt text containing backticks, quotes, ``$`` or
newlines cannot be word-split or command-substituted.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from graph_bench.backbone.agent import AgentError
from graph_bench.recorder.models import AgentTelemetry

if TYPE_CHECKING:
    from graph_bench.backbone.models import AgentTurn, RecoveryMode

_DEFAULT_TURN_TIMEOUT_S = 600.0


def _render(template: list[str], values: dict[str, str]) -> list[str]:
    """Substitute placeholders per argv element (never via a shell)."""
    out = []
    for part in template:
        rendered = part
        for key, value in values.items():
            rendered = rendered.replace('{' + key + '}', value)
        out.append(rendered)
    return out


def _transcript_text(turn: AgentTurn) -> str:
    lines = [f'{m.role}: {m.text}' for m in turn.transcript]
    lines.append(f'user: {turn.latest_user_text}')
    return '\n\n'.join(lines)


class CLIAgent:
    """Drives an external agent process, one invocation per turn."""

    def __init__(self, cfg: dict) -> None:
        command = cfg.get('command')
        if not command or not isinstance(command, list):
            msg = 'cli agent needs a non-empty "command" argv list'
            raise ValueError(msg)
        if shutil.which(command[0]) is None and not Path(command[0]).exists():
            msg = f'cli agent command not found on PATH: {command[0]!r}'
            raise ValueError(msg)
        self._cfg = cfg
        self._command = command
        self._model = cfg.get('model') or ''
        self._send = cfg.get('send', 'latest')
        self._timeout = float(
            cfg.get('turn_timeout_s', _DEFAULT_TURN_TIMEOUT_S),
        )

    def _workspace(self, turn: AgentTurn) -> str:
        root = self._cfg.get('workspace_root')
        if not root:
            return str(turn.workspace or '')
        path = Path(root) / turn.task_id
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    async def respond(
        self, turn: AgentTurn, *, mode: RecoveryMode = 'normal'
    ) -> AgentTelemetry:
        prompt = (
            _transcript_text(turn)
            if self._send == 'transcript' or mode == 'replay_history'
            else turn.latest_user_text
        )
        values = {
            'model': self._model,
            'session': turn.session_id,
            'workspace': self._workspace(turn),
            'turn': str(turn.turn_index),
            'task': turn.task_id,
        }
        argv = _render(self._command, {**values, 'prompt': prompt})

        image_arg = self._cfg.get('image_arg')
        if turn.latest_user_images:
            if not image_arg:
                # Silently dropping attachments would corrupt any
                # multimodal comparison while still producing scores.
                msg = (
                    f'{len(turn.latest_user_images)} image(s) attached but '
                    'this agent has no "image_arg" configured'
                )
                raise AgentError(msg)
            for path in turn.latest_user_images:
                argv += _render(image_arg, {**values, 'path': path})

        stdin_bytes = None
        if '{prompt}' not in ' '.join(self._command):
            stdin_bytes = prompt.encode()

        env = {**os.environ, **(self._cfg.get('env') or {})}
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE if stdin_bytes else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            raise AgentError(f'spawn failed: {exc}') from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_bytes), timeout=self._timeout,
            )
        except TimeoutError:
            # A hung turn otherwise holds a worker forever; kill it so the
            # case fails fast and the batch continues.
            proc.kill()
            await proc.wait()
            raise AgentError(
                f'turn exceeded {self._timeout:g}s',
            ) from None

        latency_ms = (time.monotonic() - start) * 1000
        text = stdout.decode(errors='replace').strip()
        err = stderr.decode(errors='replace').strip()
        if proc.returncode != 0:
            raise AgentError(
                f'exit {proc.returncode}: {err[:400] or text[:400]}',
            )
        if not text:
            raise AgentError(f'empty reply (stderr: {err[:400]})')
        return AgentTelemetry(
            text=text,
            raw_output=text,
            model=self._model or None,
            latency_ms=latency_ms,
        )

    async def aclose(self) -> None:
        return None


from graph_bench.backbone.registry import register_agent  # noqa: E402


def _cli_factory(cfg: dict) -> CLIAgent:
    return CLIAgent(cfg)


register_agent('cli', _cli_factory)
