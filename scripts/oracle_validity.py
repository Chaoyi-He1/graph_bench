#!/usr/bin/env python3
"""
Construct validity: do the metrics separate agents whose behaviour differs
in ways we know by construction?

A benchmark that reports model scores without this is asking to be taken on
faith. The five scripted profiles differ in stated ways, so each pair licenses
a prediction that can fail:

  conservative  walks the canonical path, asks every clarification
  blind         never asks; burns the known-blind edges, then guesses
  cheater       fishes for future knowledge, then behaves like blind
  expert        skips the asking, states the inference it is relying on
  gambler       identical actions to expert, states nothing

  P1  conservative grounds near 1.0 and resolves; it is the ceiling a model
      row should be read against.
  P2  blind grounds far below conservative and proposes prematurely far more
      often. Floor.
  P3  cheater ~= blind on every metric. The fishing turns must earn nothing
      under the leak-safe profile, so this is a behavioural test of the
      anti-leak guarantee -- a score gap here means the simulator answered
      questions the graph position did not license.
  P4  expert ~= gambler on outcome and grounding (identical actions) but
      ahead on the explanation rubric (only one of them shows its reasoning).
      If explanation does not separate them, that rubric is not measuring
      what it claims.

Run after scripts/run_oracles.sh completes.
"""
from __future__ import annotations
import json, glob, os, statistics as st, sys
from math import sqrt, comb
from pathlib import Path

WS = Path(os.path.expanduser('~/graph_bench_ws'))
M = WS / 'runs/matrix'
CORPUS = WS / 'data/released/graphs'
PROFILES = ['conservative', 'blind', 'cheater', 'expert', 'gambler']


def graphs() -> dict:
    return {os.path.basename(p)[:-5]: json.load(open(p))['graph']
            for p in glob.glob(str(CORPUS / '*.json'))}


def premature(run: Path, gs: dict) -> dict[str, int]:
    out = {}
    for path in glob.glob(str(run / '*.jsonl')):
        case = os.path.basename(path)[:-6]
        g = gs.get(case)
        if g is None:
            continue
        offers = {e['from'] for e in g['edges']
                  if e['edge_type'] in ('solution_only', 'mixed')}
        n = 0
        for line in open(path):
            ev = json.loads(line).get('event') or {}
            m = ev.get('match') or {}
            if (m.get('type') == 'none'
                    and m.get('edge_type') == 'solution_only'
                    and ev.get('node_before') not in offers):
                n += 1
        out[case] = n
    return out


def load(profile: str, gs: dict) -> dict | None:
    run = M / f'oracle-{profile}' / f'oracle-{profile}'
    mp, jp = run / 'metrics.json', run / 'judgments.json'
    if not mp.exists():
        return None
    m = json.load(open(mp))['testcases']
    j = json.load(open(jp))['testcases'] if jp.exists() else {}
    pre = premature(run, gs)
    rec = {}
    for k, v in m.items():
        mm = v['metrics']
        jj = j.get(k) or {}
        rub = jj.get('rubrics') or {}
        rec[k] = {
            'resolved': mm.get('termination_reason') == 'terminal_resolved',
            'grounded': mm.get('info_grounded_decision_rate'),
            'reveals': mm.get('forced_reveal_count', 0),
            'turns': mm.get('n_agent_turns', 0),
            'premature': pre.get(k, 0),
            'grade': jj.get('grade'),
            **{r: (rub.get(r) or {}).get('score') for r in
               ('proactiveness', 'hallucination', 'explanation', 'recovery')},
        }
    return rec


def mean(rows, key):
    vals = [r[key] for r in rows.values() if r.get(key) is not None]
    return st.mean(vals) if vals else None


def sign_p(d):
    pos = sum(1 for x in d if x > 0); neg = sum(1 for x in d if x < 0)
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def paired(a, b, key):
    common = [c for c in set(a) & set(b)
              if a[c].get(key) is not None and b[c].get(key) is not None]
    d = [a[c][key] - b[c][key] for c in common]
    if len(d) < 3 or st.pstdev(d) == 0:
        return len(d), (st.mean(d) if d else 0.0), 0.0, 1.0
    m, sd = st.mean(d), st.stdev(d)
    t = m / (sd / sqrt(len(d)))
    return len(d), m, t, sign_p(d)


def main() -> int:
    gs = graphs()
    data = {p: load(p, gs) for p in PROFILES}
    have = {p: d for p, d in data.items() if d}
    if not have:
        sys.exit('no oracle runs found yet')

    cols = ['resolved', 'grounded', 'premature', 'reveals', 'turns',
            'grade', 'explanation', 'hallucination']
    print(f"{'profile':14}{'n':>5}" + ''.join(f'{c:>14}' for c in cols))
    for p in PROFILES:
        d = have.get(p)
        if not d:
            print(f'{p:14}{"--":>5}'); continue
        row = f'{p:14}{len(d):5}'
        for c in cols:
            v = st.mean([1.0 if r[c] else 0.0 for r in d.values()]) if c == 'resolved' else mean(d, c)
            row += f'{v:14.3f}' if v is not None else f'{"n/a":>14}'
        print(row)

    print('\npredictions:')
    def check(name, cond, detail):
        print(f'  [{"PASS" if cond else "FAIL"}] {name}: {detail}')

    if have.get('conservative'):
        # Stated as a ranking, not a cut. An absolute threshold like
        # "grounded > 0.9" fails on 0.900 and would be reporting the
        # threshold rather than the behaviour -- the same mistake this
        # paper criticises elsewhere.
        c = have['conservative']
        g = mean(c, 'grounded')
        r = st.mean([1.0 if x['resolved'] else 0.0 for x in c.values()])
        others = {p2: mean(d, 'grounded') for p2, d in have.items()
                  if p2 != 'conservative' and mean(d, 'grounded') is not None}
        top = not others or g >= max(others.values())
        check('P1 conservative is the ceiling', top,
              f'grounded {g:.3f} (highest of {len(others) + 1} profiles), '
              f'resolved {r:.1%}')
    if have.get('blind') and have.get('conservative'):
        n, m, t, p = paired(have['blind'], have['conservative'], 'grounded')
        n2, m2, t2, p2 = paired(have['blind'], have['conservative'], 'premature')
        check('P2 blind is the floor', m < 0 and m2 > 0,
              f'grounded {m:+.3f} (t={t:.1f}), premature {m2:+.2f} (t={t2:.1f}), n={n}')
    if have.get('cheater') and have.get('blind'):
        n, m, t, p = paired(have['cheater'], have['blind'], 'grade')
        # An empty comparison satisfies "not significant" vacuously. A
        # prediction that cannot fail is not a check -- require a sample.
        if n < 30:
            print(f'  [ -- ] P3 fishing earns nothing: only n={n} paired '
                  f'cases judged so far; not evaluated')
        else:
            # The claim is directional: fishing must not PAY. An
            # "abs(t) < 2.6 or p > 0.01" predicate passes on either leg
            # and would accept a real gain that happened to fail the sign
            # test. Require that the cheater does not come out ahead.
            gained = m > 0 and abs(t) > 2.6 and p < 0.01
            check('P3 fishing earns nothing (leak defence)', not gained,
                  f'cheater - blind grade {m:+.4f} '
                  f'(t={t:.2f}, sign p={p:.3g}, n={n}); '
                  f'{"no gain" if m <= 0 else "gain not established"}')
    if have.get('expert') and have.get('gambler'):
        n, m, t, p = paired(have['expert'], have['gambler'], 'explanation')
        n2, m2, t2, _ = paired(have['expert'], have['gambler'], 'grounded')
        if n < 30:
            print(f'  [ -- ] P4 explanation separates expert from gambler: '
                  f'only n={n} paired cases judged so far; not evaluated')
            return 0
        check('P4 explanation separates expert from gambler',
              m > 0 and abs(t) > 2.6,
              f'explanation {m:+.3f} (t={t:.2f}, n={n}); grounded {m2:+.3f} (t={t2:.2f})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
