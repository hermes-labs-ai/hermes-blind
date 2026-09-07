# AGENTS.md — hermes-blind

## Product boundary

hermes-blind is a dependency-free package with two deterministic surfaces:

- prompt wrapping for evidence-gated evaluation; and
- turn-one goal extraction from Claude Code or Codex session JSONL.

It is not a model, judge, automatic drift detector, security boundary, or
proof of behavioral recovery.

## Required checks

Before proposing a change:

```bash
ruff check src tests
pytest -q
python -m build
twine check dist/*
```

Also install the built wheel in a clean environment and invoke both
`hermes-blind --help` and `hermes-blind apply --help`.

## Invariants

- Keep the runtime standard-library-only.
- Preserve caller prompts byte-for-byte at the tail of wrapped output.
- Keep `null` an exact no-op.
- Keep recovery extraction deterministic and local.
- Do not emit absolute session paths by default.
- Do not present extraction recall as evidence of downstream model recovery.
- Do not expose internal experiment harnesses through the public CLI.
- Add a regression test for every parser, extraction, or output-shape fix.
- Keep `build_anchor().markdown` byte-identical to `build_recovery_scaffold_from_user_texts()`; `ParseStats` observes, it never changes what an iterator yields.

## Release claims

Allowed: tests passed, package built, wheel installed, JSONL formats parsed,
and exact extraction-audit results with their denominator.

Not allowed without new evidence: reduces bias, detects drift, recovers model
behavior, chooses an optimal intervention turn, or resists prompt injection.
