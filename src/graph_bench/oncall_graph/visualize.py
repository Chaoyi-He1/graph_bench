"""Render a Task graph to a standalone HTML page using mermaid.js."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

from graph_bench.oncall_graph.classify import (
    edge_class as _edge_class,
)
from graph_bench.oncall_graph.classify import (
    node_class as _node_class,
)

if TYPE_CHECKING:
    from pathlib import Path

    from graph_bench.oncall_graph.models import Edge, Node, Task


def _safe_id(node_id: str) -> str:
    """Mermaid node IDs must be alnum + underscore; replace anything else."""
    return ''.join(c if c.isalnum() or c == '_' else '_' for c in node_id)


def _quote_label(text: str) -> str:
    """Wrap arbitrary text safely as a mermaid label."""
    # Mermaid double-quoted strings handle most chars; escape internal double quotes.
    cleaned = text.replace('"', '#quot;').replace('\n', ' ')
    return f'"{cleaned}"'


def _node_label(node_id: str, node: Node) -> str:
    head = node.label or node_id
    head_html = html.escape(head).replace('\n', '<br/>')
    pieces = [f'<b>{head_html}</b>']
    # Show only |info_state| count in the diagram; full list lives in
    # the table below. Keeps node boxes narrow enough that the graph
    # fits a reasonable width even with 20+ nodes.
    if node.info_state:
        pieces.append(f'<small>info: {len(node.info_state)}</small>')
    return _quote_label('<br/>'.join(pieces))


def _edge_arrow_and_label(edge: Edge) -> tuple[str, str]:
    """
    Return (arrow_syntax, label_text). Mermaid arrow with optional label.

    Components (clarification / solution) are guaranteed present per the
    Edge model's `_check_components_match_type` validator. We re-check
    here only to narrow Optional types for the type-checker.
    """
    sol = edge.solution
    if edge.edge_type == 'clarification_only':
        if not edge.clarifications:
            msg = (
                f'{edge.edge_id}: clarifications missing on '
                f'clarification_only edge'
            )
            raise ValueError(msg)
        info_ids = ', '.join(c.info_id for c in edge.clarifications)
        return '-.->', f'❓ {info_ids}'
    if edge.edge_type == 'solution_only':
        if sol is None:
            msg = f'{edge.edge_id}: solution missing on solution_only edge'
            raise ValueError(msg)
        # Shortcuts get a 🚀 prefix; known-blind takes precedence on the
        # bullet (a blind shortcut shows both 🚀 and 💥).
        prefix = ''
        if sol.is_shortcut:
            prefix += '🚀 '
            skip_n = len(sol.shortcut_skipped_info)
            tag_info = f'(skip {skip_n})'
        else:
            tag_info = ''
        if sol.is_known_blind_path:
            prefix += '💥 blind: '
        elif not sol.is_shortcut:
            prefix += '⚡ '
        return '==>', f'{prefix}{sol.intent} {tag_info}'.strip()
    # mixed
    if not edge.clarifications or sol is None:
        msg = f'{edge.edge_id}: mixed edge missing clarifications or solution'
        raise ValueError(msg)
    info_ids = ', '.join(c.info_id for c in edge.clarifications)
    return (
        '==>',
        f'🔀 ❓{info_ids} + ⚡{sol.intent}',
    )


def task_to_mermaid(task: Task) -> str:
    g = task.graph
    lines: list[str] = ['flowchart LR']

    for node_id, node in g.nodes.items():
        safe = _safe_id(node_id)
        lines.append(f'    {safe}[{_node_label(node_id, node)}]')

    edge_color = {
        'clarif': '#3b82f6',
        'solution': '#f97316',
        'blind': '#ef4444',
        'mixed': '#a855f7',
        'shortcut': '#0ea5e9',  # cyan — visually distinct from solution orange
    }

    for i, edge in enumerate(g.edges):
        src = _safe_id(edge.from_node)
        dst = _safe_id(edge.to_node)
        arrow, label = _edge_arrow_and_label(edge)
        lines.append(f'    {src} {arrow}|{_quote_label(label)}| {dst}')
        color = edge_color[_edge_class(edge)]
        lines.append(f'    linkStyle {i} stroke:{color},stroke-width:2px')

    # Node classes.
    for node_id, node in g.nodes.items():
        cls = _node_class(node_id, node, g.start_node)
        lines.append(f'    class {_safe_id(node_id)} {cls}')

    lines.extend(
        [
            '    classDef start fill:#fee2e2,stroke:#b91c1c,color:#000',
            '    classDef terminal fill:#dcfce7,stroke:#15803d,color:#000',
            '    classDef normal fill:#fef3c7,stroke:#a16207,color:#000',
        ]
    )

    return '\n'.join(lines)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose', flowchart: {{ htmlLabels: true, curve: 'basis' }} }});
  // After render, resize SVG to its natural viewBox so the graph isn't squished
  // to container width when there are many nodes.
  window.addEventListener('load', () => {{
    setTimeout(() => {{
      document.querySelectorAll('.graph svg').forEach(svg => {{
        const vb = svg.viewBox?.baseVal;
        if (vb && vb.width > 0) {{
          svg.removeAttribute('width');
          svg.removeAttribute('height');
          svg.style.width = vb.width + 'px';
          svg.style.height = vb.height + 'px';
        }}
      }});
    }}, 300);
  }});
</script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 24px; color: #111; }}
  h1 {{ margin-top: 0; }}
  .meta {{ color: #555; font-size: 0.9em; margin-bottom: 16px; }}
  .legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 8px 0 16px; font-size: 0.9em; }}
  .legend span {{ display: inline-block; padding: 4px 8px; border-radius: 4px; color: #fff; }}
  .clarif {{ background: #3b82f6; }}
  .solution {{ background: #f97316; }}
  .blind {{ background: #ef4444; }}
  .mixed {{ background: #a855f7; }}
  .shortcut {{ background: #0ea5e9; }}
  .graph {{ border: 1px solid #ddd; padding: 16px; border-radius: 8px; background: #fafafa; overflow-x: auto; }}
  .graph .mermaid {{ background: transparent; padding: 0; display: inline-block; min-width: 100%; }}
  .graph svg {{ max-width: none !important; display: block; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 24px; font-size: 0.9em; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
  th {{ background: #f3f4f6; }}
  code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 3px; font-size: 0.85em; }}
  details {{ margin: 16px 0; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  pre {{ background: #1f2937; color: #f9fafb; padding: 12px; border-radius: 6px; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{title_html}</h1>
<div class="meta">
  <div><b>task_id:</b> <code>{task_id}</code></div>
  <div><b>graph version:</b> {graph_version} &nbsp;&nbsp; <b>HITL reviewed:</b> {hitl}</div>
  {created_from_html}
</div>

<div class="legend">
  <span class="clarif">❓ clarification_only</span>
  <span class="solution">⚡ solution_only</span>
  <span class="shortcut">🚀 shortcut (auto-gen, skips clarifications)</span>
  <span class="blind">💥 known blind path</span>
  <span class="mixed">🔀 mixed</span>
</div>

<div class="graph">
<pre class="mermaid">
{mermaid}
</pre>
</div>

<h2>Satisfaction conditions</h2>
<ol>{conditions_html}</ol>

<h2>Persona hint</h2>
<div>{persona_html}</div>

<h2>Nodes</h2>
<table>
  <thead><tr><th>id</th><th>system_state</th><th>info_state</th><th>symptoms_visible</th><th>terminal</th></tr></thead>
  <tbody>{nodes_rows}</tbody>
</table>

<h2>Edges</h2>
<table>
  <thead><tr><th>id</th><th>type</th><th>from → to</th><th>clarification</th><th>solution</th></tr></thead>
  <tbody>{edges_rows}</tbody>
</table>

<details>
  <summary>Raw JSON</summary>
  <pre>{raw_json}</pre>
</details>
</body>
</html>
"""


def _escape(text: str | None) -> str:
    return html.escape(text or '')


def _format_node_row(node_id: str, node: Node) -> str:
    info = ', '.join(_escape(i) for i in node.info_state) or '—'
    symptoms = (
        '<ul>'
        + ''.join(f'<li>{_escape(s)}</li>' for s in node.symptoms_visible)
        + '</ul>'
        if node.symptoms_visible
        else '—'
    )
    return (
        f'<tr><td><code>{_escape(node_id)}</code></td>'
        f'<td>{_escape(node.system_state_id)}</td>'
        f'<td>{info}</td>'
        f'<td>{symptoms}</td>'
        f'<td>{"✅" if node.is_terminal else ""}</td></tr>'
    )


def _format_edge_row(edge: Edge) -> str:
    clar = '—'
    sol = '—'
    if edge.clarifications:
        clar = '<br/><br/>'.join(
            f'<b>info_id:</b> <code>{_escape(c.info_id)}</code><br/>'
            f'<b>level:</b> {_escape(c.level)}<br/>'
            f'<b>user answer:</b> '
            f'{_escape(c.user_answer_in_this_oncall)}'
            for c in edge.clarifications
        )
    if edge.solution is not None:
        info = edge.solution.required_info
        req = f'L1={info.L1} L2={info.L2} L3={info.L3}'
        shortcut_block = ''
        if edge.solution.is_shortcut:
            skipped = (
                ', '.join(
                    _escape(s) for s in edge.solution.shortcut_skipped_info
                )
                or '—'
            )
            hint = (
                _escape(edge.solution.inference_hint)
                or '<i>(generic — agent must justify each skipped item)</i>'
            )
            shortcut_block = (
                f'<br/><span style="color:#0ea5e9"><b>🚀 SHORTCUT</b></span><br/>'
                f'<b>skipped:</b> <code>{skipped}</code><br/>'
                f'<b>inference_hint:</b> {hint}'
            )
        flags = []
        if edge.solution.is_composite:
            flags.append('composite')
        if edge.solution.is_known_blind_path:
            flags.append('known_blind_path')
        flags_str = (' • ' + ', '.join(flags)) if flags else ''
        sol = (
            f'<b>intent:</b> {_escape(edge.solution.intent)}<br/>'
            f'<b>keywords:</b> {", ".join(_escape(k) for k in edge.solution.approach_keywords) or "—"}<br/>'
            f'<b>required_info:</b> <code>{_escape(req)}</code>{flags_str}'
            f'{shortcut_block}'
        )
    return (
        f'<tr><td><code>{_escape(edge.edge_id)}</code></td>'
        f'<td>{_escape(edge.edge_type)}</td>'
        f'<td><code>{_escape(edge.from_node)} → {_escape(edge.to_node)}</code></td>'
        f'<td>{clar}</td>'
        f'<td>{sol}</td></tr>'
    )


def task_to_html(task: Task) -> str:
    mermaid = task_to_mermaid(task)
    raw_json = json.dumps(
        task.model_dump(by_alias=True, exclude_none=True),
        indent=2,
        ensure_ascii=False,
    )
    title = task.title or task.task_id
    conditions = (
        ''.join(f'<li>{_escape(c)}</li>' for c in task.satisfaction_conditions)
        or '<li>—</li>'
    )
    persona = '—'
    if task.persona_hint is not None:
        persona = (
            f'<b>experience:</b> {_escape(task.persona_hint.experience_level)}<br/>'
            f'<b>style:</b> {_escape(task.persona_hint.communication_style)}'
        )
    nodes_rows = ''.join(
        _format_node_row(nid, n) for nid, n in task.graph.nodes.items()
    )
    edges_rows = ''.join(_format_edge_row(e) for e in task.graph.edges)
    created_from_html = (
        f'<div><b>created from:</b> <code>{_escape(task.metadata.created_from)}</code></div>'
        if task.metadata.created_from
        else ''
    )
    return HTML_TEMPLATE.format(
        title=title,
        title_html=_escape(title),
        task_id=_escape(task.task_id),
        graph_version=_escape(task.metadata.graph_version),
        hitl='yes' if task.metadata.hitl_reviewed else 'no',
        created_from_html=created_from_html,
        mermaid=mermaid,
        conditions_html=conditions,
        persona_html=persona,
        nodes_rows=nodes_rows,
        edges_rows=edges_rows,
        raw_json=html.escape(raw_json),
    )


def write_html(task: Task, out_path: Path) -> None:
    out_path.write_text(task_to_html(task), encoding='utf-8')
