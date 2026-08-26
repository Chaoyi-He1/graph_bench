# ICLR 2026 submission draft

`main.tex` against the official ICLR 2026 template (`iclr2026_conference.sty`,
`.bst`, `fancyhdr.sty`, `math_commands.tex`, unmodified from the Master-Template
repository).

Build:

```
pdflatex main && pdflatex main
```

No LaTeX toolchain was available on the machine that wrote this, so **the
draft has never been compiled.** It passes a structural check only —
balanced environments, every `\includegraphics` target present, no dangling
or unreferenced labels. Expect the first real build to surface layout work,
particularly float placement around the four figures.

Figures are copied from `paper/figures/`, which
`scripts/figures.py` regenerates from the run directories. After any re-run,
regenerate and copy again rather than editing a PDF in place.

Every number in the draft traces to `docs/results.md`, which
`scripts/results_pack.py` writes from the same runs.
