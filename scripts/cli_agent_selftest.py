#!/usr/bin/env python3
"""
Offline invariants for the CLI agent adapter (scripts/, per repo convention).

Runs against a fake agent in scripts/fixtures/, so it needs no network, no
API key and no real agent installed:

    uv run --native-tls python scripts/cli_agent_selftest.py

The shell-metacharacter case is not hypothetical. In a sibling harness a
prompt was interpolated into a shell command string, and backticks inside
it were command-substituted before the agent ever saw them. Building argv
as a list makes that class of bug unrepresentable; this checks it stays so.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

from graph_bench.agents.cli import CLIAgent  # noqa: E402
from graph_bench.backbone.agent import AgentError  # noqa: E402
from graph_bench.backbone.models import AgentTurn  # noqa: E402

FIXTURE = str(Path(__file__).resolve().parent / 'fixtures/fake_cli_agent.py')
BASE = ['python3', FIXTURE, '--model', '{model}',
        '--session', '{session}', '--prompt', '{prompt}']


def _turn(i: int, text: str, images: list[str] | None = None) -> AgentTurn:
    return AgentTurn(task_id='t1', session_id='sess-A', turn_index=i,
                     latest_user_text=text, latest_user_images=images or [])


async def _checks() -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    agent = CLIAgent({'command': BASE, 'model': 'demo-model'})

    r1 = await agent.respond(_turn(0, 'my app crashes'))
    r2 = await agent.respond(_turn(1, 'here is the log'))
    out.append(('session persists across turns',
                'turn1' in r1.text and 'turn2' in r2.text))
    out.append(('model recorded in telemetry', r1.model == 'demo-model'))

    evil = 'why does `rm -rf /` show in $HOME; also "quoted" & piped|stuff?'
    r3 = await agent.respond(_turn(2, evil))
    out.append(('shell metacharacters reach the agent intact',
                'rm -rf /' in r3.text and '$HOME' in r3.text))

    stdin_agent = CLIAgent({
        'command': ['python3', FIXTURE, '--model', '{model}',
                    '--session', '{session}'],
        'model': 'demo-model',
    })
    r4 = await stdin_agent.respond(_turn(0, 'stdin route'))
    out.append(('prompt falls back to stdin', 'stdin route' in r4.text))

    try:
        await agent.respond(_turn(3, 'please FAIL now'))
        out.append(('nonzero exit raises AgentError', False))
    except AgentError as exc:
        out.append(('nonzero exit raises AgentError', 'exit 3' in str(exc)))

    slow = CLIAgent({'command': BASE, 'model': 'm', 'turn_timeout_s': 2})
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        await slow.respond(_turn(4, 'HANG please'))
        out.append(('hung turn is killed, not waited on', False))
    except AgentError as exc:
        out.append(('hung turn is killed, not waited on',
                    'exceeded' in str(exc) and loop.time() - t0 < 8))

    try:
        await agent.respond(_turn(5, 'see this', images=['/tmp/x.png']))
        out.append(('unsupported images fail loudly', False))
    except AgentError as exc:
        out.append(('unsupported images fail loudly',
                    'image_arg' in str(exc)))
    return out


def main() -> int:
    tmp = tempfile.mkdtemp(prefix='cli-agent-selftest-')
    os.environ['FAKE_LOG'] = tmp
    try:
        results = asyncio.run(_checks())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, passed in results:
        print(f'  {"PASS" if passed else "FAIL"}  {name}')
    failed = [n for n, p in results if not p]
    print(f'{len(results) - len(failed)}/{len(results)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
