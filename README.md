# hermes-blind

**Deterministic prompt and session-recovery scaffolds for LLM workflows.**

[![PyPI](https://img.shields.io/pypi/v/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: experimental](https://img.shields.io/badge/status-experimental-orange.svg)](#evidence-and-limits)

hermes-blind provides two small, standard-library-only primitives:

1. prepend an evidence-gating scaffold to an evaluation prompt; and
2. recover a compact turn-one goal anchor from a Claude Code or Codex session log.

It makes no model calls, sends no network requests, and does not claim to
detect drift automatically.

## Install

```bash
pip install hermes-blind
```

Python 3.10+.

## Recover a long session

```bash
hermes-blind apply \
  --session /path/to/rollout.jsonl \
  --format auto \
  --anchor-mode goals \
  --turn 9 \
  --out recovery.md
```

The default `goals` mode scans the first user turn for goal-carrying
sentences and preserves up to 12 of them. Use `first-sentence` for the
legacy compact behavior or `full` to include up to 4,000 characters.
`--format auto` recognizes Claude Code and Codex JSONL shapes.

The `--turn` value is output metadata. It is not an automatic trigger and
does not imply that turn 9 is an empirically optimal intervention point.
Existing output files are preserved unless `--force` is passed; the input
session file can never be used as the output path.

Recovery output includes user-authored text. It records only the session
filename, not its absolute path, but you should still inspect the markdown
before sharing it.

## Wrap an evaluation prompt

```python
from hermes_blind import wrap

prompt = wrap(
    "Rate this paper on novelty from 0 to 10 and cite the target text.",
    variant="v1",
)
```

Or from the CLI:

```bash
hermes-blind apply --variant v1 --prompt "Score this artifact from quoted evidence."
```

Available variants are `null`, `micro`, `short`, `v1`, `full`,
`placebo`, and `gate-only`. The `null` variant is an exact no-op for
controlled comparisons.

## Rubric framing helpers

The package also exposes the dependency-free intent and scope preambles used
by hermes-rubric:

```python
from hermes_blind import compose_intent

framed = compose_intent(
    "Evaluate whether this release is ready.",
    scope_class="results-bundle",
    intent_debias=True,
)
```

## Evidence and limits

Validated mechanics for 0.1.3:

- deterministic prompt wrapping and disclosure parsing;
- Claude Code and Codex JSONL parsing;
- three recovery anchor modes;
- prompt preservation and scaffold-family invariants;
- package build, clean installation, CLI invocation, and unit tests.

A frozen 66-goal extraction audit found that goal-set extraction represented
40 of 66 pre-listed goals, compared with 7 of 66 for the previous
first-sentence heuristic: a 50.0 percentage-point increase, with improvement
in 7 of 9 sessions and ties in 2. This demonstrates substantially better
**mission representation in the generated recovery artifact**, a necessary
first step for recovery. It does not establish that reinserting the artifact
causes downstream model adherence or better task outcomes. See the
[privacy-safe evaluation report](https://github.com/hermes-labs-ai/hermes-blind/blob/main/EVALUATION.md)
for the method, sanitized
per-session results, statistical context, limitations, and receipt hashes.

Public synthetic fixtures in `tests/test_apply.py` reproduce the parsing,
extraction, safety, and output mechanics with fabricated Claude Code and Codex
JSONL. They do not reproduce the private 40/66 audit.

Not established:

- reliable bias reduction from the evaluation prefix;
- successful behavioral recovery after inserting a generated anchor;
- automatic drift detection or an optimal intervention turn;
- adversarial prompt-injection resistance;
- non-English behavior.

Earlier single-shot experiments did not establish the original bias-reduction
hypothesis. A later multi-turn research harness remains internal and is not
part of the public runtime because its efficacy study is incomplete.

Treat the output as a transparent scaffold for a human or agent to inspect,
not as a security boundary or independent evaluator.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m build
twine check dist/*
```

## Version note

0.1.3 is the first public 0.1.x release. The public comparison is therefore
**0.0.6 → 0.1.3**. Versions 0.1.0 through 0.1.2 were internal development
candidates; 0.1.3 is a patch over the unpublished 0.1.2 candidate that adds
multi-goal extraction and aligns the public package surface.

## License

MIT. See [LICENSE](LICENSE).

Part of [Hermes Labs](https://hermes-labs.ai).
