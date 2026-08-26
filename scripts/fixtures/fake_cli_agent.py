#!/usr/bin/env python3
"""Fake session-ful CLI agent: appends the prompt to a per-session file."""
import sys, os, pathlib
args = sys.argv[1:]
sess = args[args.index('--session') + 1] if '--session' in args else 'none'
model = args[args.index('--model') + 1] if '--model' in args else 'none'
prompt = args[args.index('--prompt') + 1] if '--prompt' in args else sys.stdin.read()
log = pathlib.Path(os.environ['FAKE_LOG']) / f'{sess}.log'
log.parent.mkdir(parents=True, exist_ok=True)
with log.open('a') as f:
    f.write(prompt.replace('\n', ' ')[:200] + '\n')
turns = len(log.read_text().splitlines())
if 'HANG' in prompt:
    import time; time.sleep(60)
if 'FAIL' in prompt:
    sys.stderr.write('boom\n'); sys.exit(3)
print(f'[{model}|{sess}|turn{turns}] {prompt.strip()[:80]}')
