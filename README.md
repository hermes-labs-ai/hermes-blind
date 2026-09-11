# Hermes Blind

**Recover the original goal of a long Claude Code or Codex session—and add evidence constraints to evaluation prompts.**

[![PyPI](https://img.shields.io/pypi/v/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![CI](https://github.com/hermes-labs-ai/hermes-blind/actions/workflows/ci.yml/badge.svg)](https://github.com/hermes-labs-ai/hermes-blind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/hermes-labs-ai/hermes-blind/blob/main/LICENSE)
[![Status: experimental](https://img.shields.io/badge/status-experimental-orange.svg)](#evidence-and-limits)

Long agent sessions can lose the shape of the request that started them.
Hermes Blind reads the first user turn from a local Claude Code or Codex JSONL
log and writes a compact recovery anchor you can inspect and paste back into
the session. It also provides a small prompt wrapper for evaluations that asks
the model to disclose prior exposure, quote its evidence, and hedge when the
evidence is thin.

The package is deterministic, dependency-free at runtime, and local: it makes
no model calls and sends no network requests.

## Install

For the isolated command-line app:

```bash
pipx install hermes-blind
```

Or install it into your current Python environment:

```bash
python -m pip install hermes-blind
```

Requires Python 3.10+.

### Or load the skill as a local Claude Code plugin

This repo ships a root `.claude-plugin/plugin.json`, so Claude Code can load
its `hermes-blind` skill directly from a clone via the `--plugin-dir` flag —
no marketplace and no MetaHub install required:

```bash
git clone https://github.com/hermes-labs-ai/hermes-blind
cd hermes-blind
claude --plugin-dir .
```

## Recover a long agent session

The lowest-friction path is to give your coding agent this instruction:

> Install `hermes-blind`, then run `hermes-blind apply --latest --format auto
> --turn <current-turn-number> --out recovery.md`. Show me the generated
> anchor and use it to restate my original goals before continuing. Do not
> overwrite files or share the session text.

Or run it directly:

```bash
hermes-blind apply \
  --latest \
  --format auto \
  --turn 9 \
  --out recovery.md
```

`--latest` finds this session's log instead of asking you to: the most
recently modified log under `~/.claude/projects/<this directory>` — or
`~/.codex/sessions/**/rollout-*.jsonl` — that contains a user turn, so
sub-agent-only logs are passed over. It prints the file it chose to stderr,
honors `CLAUDE_CONFIG_DIR` and `CODEX_HOME`, and exits 1 with what it looked
at rather than guessing when nothing matches or two logs are
indistinguishable. `--cwd PATH` points it at another project directory.

Naming the file yourself still works exactly as before, and is the fallback
when discovery refuses:

```bash
hermes-blind apply \
  --session /path/to/session.jsonl \
  --format auto \
  --turn 9 \
  --out recovery.md
```

The generated markdown starts like this:

```markdown
# Recovery scaffold (anchor-extracted from turn 1, applied at turn 9)

## Original anchor
- stated_goal: "Ship the onboarding flow and verify the clean install"

## Session state
- session file: rollout.jsonl
- user turns observed: 9
```

`--format auto` recognizes Claude Code and Codex JSONL shapes. Records that
are not user turns — tool results, sub-agent (sidechain) turns, slash-command
output and skill expansions, compaction summaries, and the context both tools
inject into the log (system reminders, task notifications, Codex environment
context and `AGENTS.md` instructions) — are skipped, so turn 1 is the first
thing the user typed; a `/command` is kept as typed. The default
`goals` mode preserves up to 12 goal-carrying sentences from the first user
turn; `first-sentence` keeps the compact legacy behavior and `full` includes
up to 4,000 characters.

The `--turn` value is only a label in the output. Hermes Blind does not detect
drift or decide when recovery is needed. Existing output files are preserved
unless `--force` is explicit, and the input session file can never be used as
the output path.

Recovery files include user-authored text. Inspect them before sharing.

### Re-anchor a Hermes Agent session at a chosen turn

Hermes Agent's `pre_llm_call` shell-hook contract can inject a recovery
anchor without writing the conversation to another file. Choose the turn
explicitly in `~/.hermes/config.yaml`:

```yaml
hooks:
  pre_llm_call:
    - command: "hermes-blind hermes-agent-hook --at-turn 9"
      timeout: 5
```

Hermes Agent asks for consent the first time it runs a shell hook. At the
selected turn, Blind reads the hook payload on stdin and returns a compact
`context` block on stdout. On other turns, malformed input, or an unsupported
payload it returns an empty object and the agent proceeds unchanged.

The turn is a user-chosen intervention point, not a detected drift event or an
efficacy threshold. The injected anchor is ephemeral and may contain text from
the first user turn; do not treat it as a security boundary.

### Machine-readable result envelope

The same extraction can be emitted as a Hermes Reliability Lab result
envelope — the markdown scaffold embedded verbatim, plus the facts it was
rendered from, tool version, a hash of the exact input bytes, one finding per
thing worth knowing, the exit code, a timestamp, and the Git commit when run
from a checkout:

```bash
python -m hermes_blind.evidence --session /path/to/session.jsonl --format auto
python -m hermes_blind.evidence --latest
```

Extraction is unchanged; what is added is observability. Lines that do not
parse are counted and reported (`input.unparseable-lines`) instead of only
being skipped; two user turns before the first assistant reply are reported
(`input.ambiguous-initial-turn`) and turn 1 is still the anchor; a file with
no user turn is the product's own error, exit 1, with no anchor invented. The
emitter reads exactly the one file it is given and discovers nothing; `--latest`
resolves the path first, in the CLI, and prints it. Either way the path appears
in the record by basename only.

## Add evidence constraints to an evaluation prompt

From the CLI:

```bash
hermes-blind apply \
  --variant v1 \
  --prompt "Score this release from quoted evidence."
```

This prints a wrapped prompt without calling a model:

```text
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]

Score this release from quoted evidence.
```

Or use the Python API:

```python
from hermes_blind import wrap

prompt = wrap(
    "Rate this paper on novelty from 0 to 10 and cite the target text.",
    variant="v1",
)
```

Available variants are `null`, `micro`, `short`, `v1`, `full`, `placebo`, and
`gate-only`. The `null` variant is an exact no-op for controlled comparisons.
The package also exposes the dependency-free intent and scope preambles used
by [Hermes Rubric](https://github.com/hermes-labs-ai/hermes-rubric).

## Evidence and limits

The repository tests and CI cover deterministic wrapping, Claude Code and
Codex JSONL parsing, recovery modes, safe output handling, package
installation, and CLI invocation.

A frozen nine-session extraction audit found that the default goal-set anchor
represented 40 of 66 pre-listed goals, compared with 7 of 66 for the earlier
first-sentence heuristic. That supports better mission representation in the
generated artifact for the evaluated sessions. It does **not** establish that
reinserting the artifact changes model behavior or improves task outcomes.
See the [evaluation report](https://github.com/hermes-labs-ai/hermes-blind/blob/main/EVALUATION.md)
for the method, limitations, sanitized results, and receipt hashes.

Not established:

- reliable bias reduction from the evaluation prefix;
- successful behavioral recovery after inserting an anchor;
- automatic drift detection or an optimal intervention turn;
- adversarial prompt-injection resistance; or
- non-English behavior.

Treat the output as a transparent scaffold for a human or agent to inspect,
not as a security boundary or independent evaluator.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m build
twine check dist/*
```

See the [changelog](https://github.com/hermes-labs-ai/hermes-blind/blob/main/CHANGELOG.md)
for release history and the
[contribution guide](https://github.com/hermes-labs-ai/hermes-blind/blob/main/CONTRIBUTING.md)
for contribution guidance.

## License

MIT. See the [license](https://github.com/hermes-labs-ai/hermes-blind/blob/main/LICENSE).

Built by [Hermes Labs](https://hermes-labs.ai).
