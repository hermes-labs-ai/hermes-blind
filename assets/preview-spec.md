# Preview asset — spec

Static terminal-card preview. Real output. No GIFs, no fake UI, no stock art.

## Dimensions

- **1280 × 720** (16:9, GitHub social preview ratio)
- 2x pixel density for retina

## Theme

- Background: `#0d1117` (GitHub dark)
- Terminal foreground: `#c9d1d9`
- Prompt glyph: `#58a6ff` (GitHub blue)
- Scaffold block text: `#7ee787` (GitHub green) — visually distinguishes the
  wrapped scaffold from the caller's prompt
- Caller prompt text: `#c9d1d9` (same as foreground)

## Font

- Monospace: `JetBrains Mono`, fallback `Menlo`, fallback `Consolas`
- Size: 16pt
- Weight: Regular for output, Bold for the `$` prompt glyph

## Padding

- 48px on all sides inside the terminal card
- 24px gap between the command line and the output block

## Card

- 24px corner radius
- Soft drop shadow: `rgba(0, 0, 0, 0.3)` blur 32px offset (0, 8px)

## Command shown

```
$ python -c "from hermes_blind import wrap; print(wrap('Score this paper on novelty 0-10.'))"
```

## Output shown

```
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]

Score this paper on novelty 0-10.
```

## Reuse rule for future Hermes micro-tools

Every hermes-* micro-tool repo uses this format:

1. Same dimensions (1280 × 720)
2. Same theme (GitHub dark, prompt blue, distinct color for tool output)
3. Same font (JetBrains Mono 16pt)
4. Real CLI or `python -c` output — never a mock screenshot
5. One command, one output block, no narration

If a future repo cannot produce a clean single-command preview, ship
`preview-source.txt` (the raw text) plus this spec and let downstream tooling
render it.

## Source text

See `preview-source.txt` for a rendering-ready plain-text version.
