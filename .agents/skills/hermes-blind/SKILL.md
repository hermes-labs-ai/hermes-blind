---
name: hermes-blind
description: Use when you need to recover the original goal of a long Claude Code or Codex session from its first user turn so you can restate it before continuing, or when you need a prompt wrapper that adds evidence and hedging constraints to evaluation prompts. Deterministic, local, no model calls. Experimental.
license: MIT
compatibility: Requires Python 3.10+; installs via `pip install hermes-blind`, executable name is `hermes-blind`. Recovery mode reads Claude Code/Codex session JSONL directly from disk; wrapper mode needs no session log or network access.
---

# hermes-blind

hermes-blind is a deterministic, local, zero-model-call tool with two modes:
recovering the original goal of a long Claude Code or Codex session from its
first user turn (so a stalled or drifted session can be restated), and
wrapping an evaluation prompt with evidence and hedging constraints before
it reaches a judge model. Experimental.

## Use it for

- Recovering the first-turn goal from a Claude Code or Codex session JSONL,
  `--latest` or `--session <path>`, to restate a long session's original
  intent
- Wrapping a prompt (`apply --prompt` or via stdin) with an evidence/hedging
  scaffold before sending it to a judge or evaluator
- Choosing among scaffold variants (`full`, `gate-only`, `micro`, `null`,
  `placebo`, `short`, `v1`) to test how much scaffold text actually changes
  judge behavior

## Do not use it for

- A general-purpose prompt library or prompt-management tool
- Recovering goals from arbitrary text — recovery mode is specific to
  Claude Code/Codex session JSONL structure
- Anything requiring a live model call — hermes-blind itself never calls one

## Quickstart

```bash
pip install hermes-blind
hermes-blind apply --prompt "Assess whether this PR is safe to merge." --variant v1
```

Real output:

```
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]

Assess whether this PR is safe to merge.
```

Recovery mode against the newest local session log:

```bash
hermes-blind apply --latest --format claude
```

## Commands

```
hermes-blind apply --prompt "<text>" --variant <full|gate-only|micro|null|placebo|short|v1>
hermes-blind apply --session <path-to-jsonl> [--turn N] [--anchor-mode first-sentence|goals|full]
hermes-blind apply --latest [--cwd <dir>] [--format auto|claude|codex]
hermes-blind hermes-agent-hook --at-turn N
```

## Output shape

- Wrapper mode (`--prompt`): the scaffold text followed by the original
  prompt, unchanged apart from the wrapper
- Recovery mode (`--session`/`--latest`): the recovered first-turn goal
  anchored per `--anchor-mode`, written to stdout or `--out`
- No JSON schema is emitted by default — output is plain text meant to be
  fed directly into a subsequent prompt

## Common gotchas

- There is no `--version` flag; use `hermes-blind --help` to confirm the
  installed CLI surface instead.
- Recovery mode expects the exact Claude Code (`~/.claude/projects/...`) or
  Codex (`~/.codex/sessions/...`) JSONL layout — arbitrary JSONL will not
  parse correctly; use `--format` to disambiguate when auto-detection is
  ambiguous.
- This tool never calls a model itself; it prepares text for a call made
  elsewhere. It does not verify anything about the target it wraps.

## More

Full docs and variant reference: https://github.com/hermes-labs-ai/hermes-blind
