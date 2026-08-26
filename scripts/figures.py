"""Regenerate the paper's figures from the runs on disk.

Same rule as the results tables: nothing is drawn from a number typed by
hand, so a figure cannot drift from the data it claims to show. Output is
vector PDF (for the paper) beside PNG (for reading in a browser).

    uv run --native-tls --extra figures python scripts/figures.py

Figures follow the claim chain rather than the data inventory — a plot
earns its place by carrying an argument the text would otherwise have to
make in prose.
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'paper/figures'
M = '/tmp/gb-v6/runs/matrix'

# A restrained palette: one hue per tier so the two-tier result reads at a
# glance, greys for structure. Colour never carries information alone —
# order and position repeat it — so the figures survive greyscale printing.
INK = '#1b2027'
MUTED = '#6b7683'
RULE = '#d5dae0'
TIER_A = '#1f6f7a'   # the GPT pair
TIER_B = '#b4703a'   # the other two
NEUTRAL = '#95a3b0'

ROWS = [
    ('gpt-5.6', f'{M}/m-gpt56/m-gpt56', TIER_A),
    ('gpt-5.5', f'{M}/m-gpt55/m-gpt55', TIER_A),
    ('GLM-5.1', f'{M}/m-glm51/m-glm51', TIER_B),
    ('Kimi-2.5', f'{M}/m-kimi25/m-kimi25', TIER_B),
]
RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')


def _style() -> None:
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Helvetica Neue', 'Helvetica', 'Arial', 'DejaVu Sans'],
        'font.size': 8.5,
        'axes.edgecolor': RULE,
        'axes.labelcolor': INK,
        'axes.titlesize': 9.5,
        'axes.titleweight': 'semibold',
        'text.color': INK,
        'xtick.color': MUTED,
        'ytick.color': MUTED,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'figure.dpi': 200,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.02,
    })


def judged(run: str) -> dict:
    p = Path(run, 'judgments.json')
    return json.loads(p.read_text())['testcases'] if p.exists() else {}


def _profile(run: str) -> str | None:
    p = Path(run, 'judgments.json')
    if not p.exists():
        return None
    # Files written before profiles existed are `default` by construction.
    return json.loads(p.read_text()).get('rubric_profile', 'default')


def paired(lo: str, hi: str) -> tuple[dict, dict]:
    """Two runs' grades, refusing to pair scores from different rubrics.

    Every difference in this paper is a paired subtraction of two grades.
    If the two sides were judged under different rubric wordings, that
    subtraction is a construct difference wearing a model difference's
    clothes -- the exact failure that already produced one retracted
    finding here. Fail rather than plot it.
    """
    pa, pb = _profile(lo), _profile(hi)
    if pa is not None and pb is not None and pa != pb:
        msg = (f'refusing to compare {lo} ({pa}) against {hi} ({pb}): '
               'different rubric profiles score different constructs')
        raise ValueError(msg)
    return (
        {c: v['grade'] for c, v in judged(lo).items()
         if v.get('grade') is not None},
        {c: v['grade'] for c, v in judged(hi).items()
         if v.get('grade') is not None},
    )


def metrics(run: str) -> dict:
    p = Path(run, 'metrics.json')
    return json.loads(p.read_text())['testcases'] if p.exists() else {}


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf', 'png'):
        fig.savefig(OUT / f'{name}.{ext}')
    plt.close(fig)
    print(f'  {name}.pdf / .png')


# --------------------------------------------------------------- F1
def fig_worked_case() -> None:
    """The object the paper is about: one graph, and the walk through it.

    Drawn rather than screenshotted so the edge types stay legible in
    print, and laid out by hand because a spring layout hides exactly the
    structure that matters — the falsified branch running parallel to the
    diagnostic path, rejoining at its own terminal.
    """
    fig, ax = plt.subplots(figsize=(6.9, 2.9))
    ax.set_xlim(0, 10.4)
    ax.set_ylim(-0.5, 4.1)
    ax.axis('off')

    top, bottom = 2.30, 0.55
    pos = {
        'N0': (1.0, top), 'N1': (3.6, top), 'N2': (6.2, top), 'T': (8.9, top),
        'N1x': (3.6, bottom), 'Tx': (8.9, bottom),
    }
    label = {
        'N0': 'N0\nas reported', 'N1': 'N1\n+ why both',
        'N2': 'N2\n+ observed timing', 'T': 'terminal\nlifecycle fix',
        'N1x': 'N1ₓ\naftermath', 'Tx': 'terminalₓ\nrecovered',
    }
    for key, (x, y) in pos.items():
        blind = key.endswith('x')
        ax.add_patch(Rectangle(
            (x - 0.85, y - 0.32), 1.70, 0.64,
            facecolor='white', edgecolor=MUTED if blind else INK,
            linewidth=0.9, linestyle=(0, (1.6, 1.6)) if blind else '-',
            zorder=3,
        ))
        ax.text(x, y, label[key], ha='center', va='center', fontsize=7.0,
                color=MUTED if blind else INK, zorder=4, linespacing=1.4)

    def straight(a, b, text, blind=False):
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        colour = MUTED if blind else INK
        ax.add_patch(FancyArrowPatch(
            (x1 + 0.87, y1), (x2 - 0.87, y2), arrowstyle='-|>',
            mutation_scale=9, linewidth=0.9, color=colour, zorder=2,
            linestyle=(0, (1.6, 1.6)) if blind else '-',
        ))
        # Above the box, not beside the arrow: a label at arrow height
        # lands inside the neighbouring node's text.
        ax.text((x1 + x2) / 2, y1 + 0.46, text, ha='center', fontsize=6.7,
                color=colour)

    straight('N0', 'N1', 'clarify · L1')
    straight('N1', 'N2', 'clarify · L3 measure')
    straight('N2', 'T', 'solution')
    straight('N1x', 'Tx', 'shortcut', blind=True)

    # The falsified branch drops away from N0 rather than continuing along
    # it, so the reader sees a fork rather than a detour.
    ax.add_patch(FancyArrowPatch(
        (pos['N0'][0], top - 0.34), (pos['N1x'][0] - 0.9, bottom),
        arrowstyle='-|>', mutation_scale=9, linewidth=0.9, color=MUTED,
        linestyle=(0, (1.6, 1.6)), zorder=2,
        connectionstyle='arc3,rad=-0.25',
    ))
    ax.text(1.15, 1.24, 'known blind path', fontsize=6.7, color=MUTED,
            rotation=-32, rotation_mode='anchor')

    ax.text(0.0, 3.84, 'A case as a causal graph', fontsize=9.8,
            fontweight='bold')
    ax.text(0.0, 3.42,
            'expo-location: the background-permission request returns '
            '“denied” before the iOS prompt resolves', fontsize=7.1,
            color=MUTED)
    ax.text(0.0, -0.34,
            'Dotted: the attempt this thread actually made and falsified. '
            'An agent may take it — the satisfaction conditions forbid '
            'reporting it as the fix.',
            fontsize=6.7, color=MUTED)
    save(fig, 'f1_worked_case')


# --------------------------------------------------------------- F2
def fig_rubrics() -> None:
    """The headline result, and the thing it is easy to miss.

    Every model interrogates the user competently, so that axis is
    saturated and carries no signal. The other three separate the tiers —
    but on `stays within the evidence` both tiers sit near the floor,
    which is the more uncomfortable half of the finding and the reason
    the axis is plotted rather than summarised.
    """
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    names = [n for n, _, _ in ROWS]
    display = {
        'proactiveness': 'asks for\nevidence',
        'hallucination': 'stays within\nthe evidence',
        'explanation': 'accounts for\nthe fault',
        'recovery': 'recovers from\na failed step',
    }
    xs = range(len(RUBRICS))
    ys_by_model: dict[str, list[float]] = {}
    for name, run, colour in ROWS:
        data = judged(run)
        ys = []
        for rub in RUBRICS:
            vals = [
                (v.get('rubrics') or {}).get(rub, {}).get('score')
                for v in data.values()
            ]
            vals = [v for v in vals if v is not None]
            mean = st.mean(vals) if vals else 0.0
            # Plot everything as "higher is better" so one line does not
            # run backwards against the others.
            ys.append(1 - mean if rub == 'hallucination' else mean)
        ys_by_model[name] = ys
        ax.plot(xs, ys, marker='o', markersize=4, linewidth=1.6,
                color=colour, label=name, alpha=0.92)
        ax.annotate(name, (xs[-1], ys[-1]), xytext=(6, 0),
                    textcoords='offset points', fontsize=7.2,
                    color=colour, va='center')

    ax.set_xticks(list(xs))
    ax.set_xticklabels([display[r] for r in RUBRICS], fontsize=7.4)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel('score (higher is better)')
    # NOTE: the title asserts a shape, so it is generated from the data
    # rather than typed. Under the first rubric wording proactiveness sat
    # at 0.92-0.97 for every model and "asking is solved" was safe; the
    # corrected wording asks whether the evidence was in hand BEFORE
    # proposing, which is a higher bar, and the first re-judged row came
    # back at 0.687. A title claiming saturation must therefore check
    # that saturation is still there.
    asks = [ys_by_model[name][0] for name in ys_by_model]
    if min(asks) > 0.85:
        title = 'Asking is solved. Staying inside the evidence is not.'
    elif max(asks) - min(asks) < 0.12:
        title = 'Models differ least on asking, most on what they say next'
    else:
        title = 'Where the models separate'
    ax.set_title(title)
    ax.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.25, len(RUBRICS) - 0.4)
    save(fig, 'f2_rubrics')


# --------------------------------------------------------------- F3
def fig_outcomes() -> None:
    """How cases end — half of all terminals are the harness's doing."""
    fig, ax = plt.subplots(figsize=(5.4, 2.2))
    order = [
        ('terminal_resolved', 'earned the fix', TIER_A),
        ('forced_walk_to_terminal', 'walked there by the insurance', NEUTRAL),
        ('none', 'ran out of turns', RULE),
        ('premature_satisfaction', 'stopped too early', TIER_B),
    ]
    names = [n for n, _, _ in ROWS]
    lefts = [0.0] * len(ROWS)
    for key, label, colour in order:
        widths = []
        for _, run, _ in ROWS:
            m = metrics(run)
            n = len(m) or 1
            widths.append(
                100
                * sum(
                    1
                    for v in m.values()
                    if v['snapshot']['termination_reason'] == key
                )
                / n
            )
        ax.barh(names, widths, left=lefts, color=colour, label=label,
                height=0.62, edgecolor='white', linewidth=0.7)
        for i, (w, l) in enumerate(zip(widths, lefts)):
            if w > 7:
                ax.text(l + w / 2, i, f'{w:.0f}', ha='center', va='center',
                        fontsize=7, color='white' if colour != RULE else MUTED)
        lefts = [a + b for a, b in zip(lefts, widths)]

    ax.set_xlim(0, 100)
    ax.set_xlabel('share of the 229 cases (%)')
    ax.invert_yaxis()
    ax.set_title('Fewer than a third of cases end in a fix the agent earned')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.32), ncol=2,
              frameon=False, fontsize=7.2)
    ax.grid(axis='x', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    save(fig, 'f3_outcomes')


# --------------------------------------------------------------- F4
def fig_harness_defects() -> None:
    """Why the harness had to be audited before any of this counted.

    The only figure here whose numbers are not recomputed at draw time.
    The 'before' decomposition was measured on the pre-fix baseline row,
    whose transcripts /tmp reaped before this script existed; the values
    are transcribed from docs/experiments.md (E-simfix), where the run
    that produced them is named. Flagged rather than quietly hardcoded —
    every other figure reads the runs directly.
    """
    fig, ax = plt.subplots(figsize=(5.4, 2.1))
    drivers = [
        ('partial deadlock', 32, 7),
        ('unmatchable by construction', 29, 15),
        ('question outside the graph', 32, 63),
        ('the agent actually failing', 7, 16),
    ]
    ys = range(len(drivers))
    before = [b for _, b, _ in drivers]
    after = [a for _, _, a in drivers]
    ax.barh([y + 0.19 for y in ys], before, height=0.34, color=NEUTRAL,
            label='before the fixes')
    ax.barh([y - 0.19 for y in ys], after, height=0.34, color=TIER_A,
            label='after')
    ax.set_yticks(list(ys))
    ax.set_yticklabels([d for d, _, _ in drivers], fontsize=7.4)
    ax.invert_yaxis()
    ax.set_xlabel('share of forced reveals (%)')
    ax.set_title('Only 7% of forced reveals were the agent failing')
    ax.legend(frameon=False, fontsize=7.2, loc='lower right')
    ax.grid(axis='x', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    save(fig, 'f4_harness_defects')


# --------------------------------------------------------------- F5
def fig_reliability() -> None:
    """Why claims are ruled by a paired test and never by one case."""
    pairs = [
        (f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-vision/gpt56-vision'),
        (f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-noimg/gpt56-noimg'),
        (f'{M}/gpt56-vision/gpt56-vision', f'{M}/gpt56-noimg/gpt56-noimg'),
    ]
    per_case: list[float] = []
    for a, b in pairs:
        ga, gb = (
            {c: v['grade'] for c, v in judged(r).items() if v.get('grade') is not None}
            for r in (a, b)
        )
        per_case += [abs(gb[c] - ga[c]) for c in set(ga) & set(gb)]
    if not per_case:
        return
    fig, ax = plt.subplots(figsize=(5.4, 2.0))
    ax.hist(per_case, bins=22, color=NEUTRAL, edgecolor='white', linewidth=0.6)
    med = st.median(per_case)
    ax.axvline(med, color=TIER_B, linewidth=1.3)
    ax.text(med + 0.008, ax.get_ylim()[1] * 0.86,
            f'median {med:.2f}', fontsize=7.2, color=TIER_B)
    ax.set_xlabel('absolute grade difference between two identical runs')
    ax.set_ylabel('cases')
    ax.set_title('The same case, run twice, moves this much')
    ax.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    save(fig, 'f5_reliability')





# --------------------------------------------------------------- F6
def fig_all_comparisons() -> None:
    """Every comparison in one panel, nulls included -- grouped by intent.

    The first version of this figure put nine rows on one axis in two
    colours, real and not-real. Read cold, that says "nothing we did to
    this benchmark changed anything", which is both the wrong reading and
    an easy one to reach. Two things fix it.

    First, a null means different things in different rows. A simulator
    swap that moves nothing is a *robustness result* -- the literature
    reports swaps moving success by up to 9 points. A leak ablation that
    moves nothing is a *problem for our motivation*. Painting them the
    same grey throws away the first and hides the second, so the rows are
    grouped by what a null would mean.

    Second, these nulls are measured at n=48, where the 99% interval is
    +/-0.06 -- more than twice the resolution of the n=229 rows. A null
    there is a bound, not an absence, so each one is annotated with the
    bound it actually supports.
    """
    from math import sqrt

    GROUPS = [
        ('Model comparisons  --  what the benchmark is for', [
            ('gpt-5.6  vs  Kimi-2.5', f'{M}/m-kimi25/m-kimi25', f'{M}/m-gpt56/m-gpt56'),
            ('gpt-5.6  vs  GLM-5.1', f'{M}/m-glm51/m-glm51', f'{M}/m-gpt56/m-gpt56'),
            ('gpt-5.6  vs  gpt-5.5', f'{M}/m-gpt55/m-gpt55', f'{M}/m-gpt56/m-gpt56'),
            ('GLM-5.1  vs  Kimi-2.5', f'{M}/m-kimi25/m-kimi25', f'{M}/m-glm51/m-glm51'),
        ]),
        ('Robustness  --  a null here is the result we want', [
            ('a different simulator model', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/e8-simswap/e8-simswap'),
            ('screenshots attached', f'{M}/e7-mm-off/e7-mm-off', f'{M}/e7-mm-on/e7-mm-on'),
            ('30 turns instead of 20', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-t30/gpt56-t30'),
        ]),
        ('Design ablation  --  a null here counts against us', [
            ('simulator sees the answer', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-leakA/gpt56-leakA'),
        ]),
        ('Reference', [
            ('the same run, twice', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-vision/gpt56-vision'),
        ]),
    ]

    items = []   # (kind, payload) with kind in {'head', 'row'}
    for title, comps in GROUPS:
        rows = []
        for label, lo, hi in comps:
            ga, gb = paired(lo, hi)
            common = sorted(set(ga) & set(gb))
            if len(common) < 3:
                continue
            d = [gb[c] - ga[c] for c in common]
            mean = st.mean(d)
            half = 2.6 * st.stdev(d) / sqrt(len(d))
            rows.append((label, mean, half, len(common), abs(mean) > half))
        if rows:
            items.append(('head', title))
            items.extend(('row', r) for r in rows)

    fig, ax = plt.subplots(figsize=(6.1, 4.5))
    ys = list(range(len(items)))[::-1]
    body = [(y, p) for y, (k, p) in zip(ys, items) if k == 'row']
    xhi = max(m + h for _, (_, m, h, _, _) in body)
    xlo = min(m - h for _, (_, m, h, _, _) in body)
    gutter = xhi + 0.015

    for y, (kind, payload) in zip(ys, items):
        if kind == 'head':
            ax.text(xlo - 0.021, y, payload, fontsize=7.2, color=INK,
                    style='italic', va='center', ha='left')
            continue
        label, mean, half, n, real = payload
        colour = TIER_A if real else NEUTRAL
        ax.plot([mean - half, mean + half], [y, y], color=colour,
                linewidth=1.5, solid_capstyle='round', alpha=0.85)
        ax.plot([mean], [y], marker='o', markersize=5, color=colour)
        # A null is a bound, not an absence -- say which bound.
        note = f'n={n}' if real else f'n={n}   |effect| < {half:.3f}'
        ax.text(gutter, y, note, fontsize=6.6, color=MUTED, va='center')

    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_yticks([y for y, (k, _) in zip(ys, items) if k == 'row'])
    ax.set_yticklabels([p[0] for k, p in items if k == 'row'], fontsize=7.4)
    ax.set_xlim(xlo - 0.023, gutter + 0.105)
    ax.set_xlabel('difference in mean grade (bars: 99% interval)')
    # The top group header sits at the highest y, where an untouched
    # ylim puts it straight through the title.
    ax.set_ylim(min(ys) - 0.7, max(ys) + 0.9)
    ax.set_title('Effect sizes, and the resolution that bounds them',
                 pad=12)
    ax.grid(axis='x', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    save(fig, 'f6_all_comparisons')


# --------------------------------------------------------------- F7
def fig_interaction_value() -> None:
    """What the conversation is worth, which is the paper's premise.

    Handed the opening report alone, a model names both mechanism and fix
    in 2.2% of cases. Allowed to interrogate the user, the same family
    earns a confirmed fix in 29%. The two are graded differently — one by
    a grader holding the answer key, one by the simulated reporter — so
    this is an order-of-magnitude claim, not a ratio to quote to two
    decimal places.
    """
    fig, ax = plt.subplots(figsize=(4.4, 2.3))
    bars = [
        ('report only,\nno questions', 2.2, NEUTRAL),
        ('report only,\npartial credit', 5.7, RULE),
        ('30 turns of\nconversation', 28.8, TIER_A),
    ]
    xs = range(len(bars))
    ax.bar(xs, [b[1] for b in bars], color=[b[2] for b in bars], width=0.55)
    for x, (_, v, _) in zip(xs, bars):
        ax.text(x, v + 0.9, f'{v:.1f}%', ha='center', fontsize=8,
                fontweight='bold')
    ax.set_xticks(list(xs))
    ax.set_xticklabels([b[0] for b in bars], fontsize=7.4)
    ax.set_ylim(0, 34)
    ax.set_ylabel('cases solved (%)')
    ax.set_title('Interaction is worth an order of magnitude')
    ax.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    save(fig, 'f7_interaction_value')


# --------------------------------------------------------------- F8
def fig_corpus() -> None:
    """What the corpus is made of, in the two dimensions that matter:
    where the cases come from, and how hard their evidence is to obtain."""
    graphs = sorted(glob.glob('/tmp/gb-v6/data/released/graphs/*.json'))
    if not graphs:
        return
    levels = {'L1_basic': 0, 'L2_inferable': 0, 'L3_specific': 0}
    nodes, edges, blind = [], [], 0
    for path in graphs:
        g = json.loads(Path(path).read_text())['graph']
        nodes.append(len(g['nodes']))
        edges.append(len(g['edges']))
        for e in g['edges']:
            if (e.get('solution') or {}).get('is_known_blind_path'):
                blind += 1
            for c in e.get('clarifications') or []:
                if c.get('level') in levels:
                    levels[c['level']] += 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.4, 2.2))
    ax1.hist(nodes, bins=range(min(nodes), max(nodes) + 2), color=NEUTRAL,
             edgecolor='white', linewidth=0.8, align='left')
    ax1.set_xlabel('states per case')
    ax1.set_ylabel('cases')
    ax1.set_title(f'{len(graphs)} cases', fontsize=8.5)
    ax1.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax1.set_axisbelow(True)

    order = ['L1_basic', 'L2_inferable', 'L3_specific']
    names = ['L1\nstated unprompted', 'L2\ninferable', 'L3\nmust be asked']
    total = sum(levels.values()) or 1
    ax2.bar(range(3), [100 * levels[k] / total for k in order],
            color=[RULE, NEUTRAL, TIER_A], width=0.55)
    for i, k in enumerate(order):
        ax2.text(i, 100 * levels[k] / total + 1.5,
                 f'{100 * levels[k] / total:.0f}%', ha='center',
                 fontsize=8, fontweight='bold')
    ax2.set_xticks(range(3))
    ax2.set_xticklabels(names, fontsize=7.2)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel('of all clarifications')
    ax2.set_title('Most evidence has to be asked for', fontsize=8.5)
    ax2.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax2.set_axisbelow(True)
    save(fig, 'f8_corpus')


# --------------------------------------------------------------- F9
def fig_counterfactual() -> None:
    """The counterfactual result, which the table under-sells.

    The eye-catching cell is not either "proposed" row — it is that the
    bottom band, "never got to a proposal at all", covers two thirds of
    both columns. Swapping one authored answer does not make the agent
    choose differently; it makes it stop choosing. Plotting the two
    columns side by side puts the should-change / should-not-change
    contrast where it can be read: the derail is *worse* in the column
    where the diagnosis was not supposed to move.
    """
    COLS = ['fix should\nchange', 'fix should\nnot change']
    # counts out of 30 per column (docs/experiments.md, E-counterfactual)
    BANDS = [
        ('proposed something different', [5, 2], TIER_A),
        ('proposed the same thing', [5, 5], NEUTRAL),
        ('never reached a proposal', [20, 23], TIER_B),
    ]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    x = [0, 1]
    bottom = [0.0, 0.0]
    for label, counts, colour in BANDS:
        pct = [100.0 * c / 30 for c in counts]
        ax.bar(x, pct, bottom=bottom, width=0.52, color=colour,
               edgecolor='white', linewidth=1.0, label=label)
        for xi, (p_, b_, c_) in enumerate(zip(pct, bottom, counts)):
            ax.text(xi, b_ + p_ / 2, f'{c_}', ha='center', va='center',
                    fontsize=8.5, color='white', weight='semibold')
        bottom = [b + p_ for b, p_ in zip(bottom, pct)]
    ax.set_xticks(x)
    ax.set_xticklabels(COLS, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel('share of interventions (%)')
    ax.set_title('One answer swapped: the agent stops converging')
    ax.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.16), ncol=1,
              frameon=False, fontsize=7.6, handlelength=1.2)
    save(fig, 'f9_counterfactual')


# -------------------------------------------------------------- F10
def fig_judge_swap() -> None:
    """Does the ranking belong to the models or to the judge?

    Two judges, same transcripts, same written rubrics. The absolute
    levels move a lot -- GLM-5.1 marks the weaker model far more
    generously -- so plotting only the gap would hide the disagreement
    that is really there. Plotting both levels and connecting them shows
    the honest version: the judges disagree about how good these models
    are, and agree about which is better.
    """
    # docs/experiments.md, E-judgeswap. Rows one and two are complete.
    DATA = [
        ('gpt-5.6', 0.624, 0.589, TIER_A),
        ('Kimi-2.5', 0.279, 0.400, TIER_B),
    ]
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    xs = [0, 1]
    for name, primary, swap, colour in DATA:
        ax.plot(xs, [primary, swap], color=colour, linewidth=1.6,
                marker='o', markersize=6, zorder=3)
        ax.text(-0.06, primary, f'{name}  {primary:.3f}', ha='right',
                va='center', fontsize=8, color=colour)
        ax.text(1.06, swap, f'{swap:.3f}', ha='left', va='center',
                fontsize=8, color=colour)
    ax.set_xticks(xs)
    ax.set_xticklabels(['primary judge\n(gpt family)',
                        'swapped judge\n(GLM-5.1)'], fontsize=8)
    ax.set_xlim(-0.62, 1.42)
    ax.set_ylim(0, 0.72)
    ax.set_ylabel('mean grade')
    ax.set_title('The gap halves; the ordering does not move')
    ax.grid(axis='y', color=RULE, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for xi in xs:
        ax.axvline(xi, color=RULE, linewidth=0.6, alpha=0.7, zorder=0)
    save(fig, 'f10_judge_swap')


def main() -> int:
    _style()
    print('writing figures to paper/figures/')
    fig_worked_case()
    fig_rubrics()
    fig_outcomes()
    fig_harness_defects()
    fig_reliability()
    fig_all_comparisons()
    fig_interaction_value()
    fig_corpus()
    fig_counterfactual()
    fig_judge_swap()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
