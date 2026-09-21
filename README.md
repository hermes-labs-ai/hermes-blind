<div align="center">

<h1>Hermes Blind</h1>

<img src="assets/hermes-blind-banner.jpg" alt="Hermes Blind — a winged guide in a blindfold travelling toward an illuminated doorway" width="960" />

<p><strong>Recover the original goal of a long coding-agent session before the context around it gets noisy.</strong></p>

<p>
<a href="https://pypi.org/project/hermes-blind/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/hermes-blind.svg"></a>
<a href="https://pypi.org/project/hermes-blind/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/hermes-blind.svg"></a>
<a href="https://github.com/hermes-labs-ai/hermes-blind/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/hermes-labs-ai/hermes-blind/actions/workflows/ci.yml/badge.svg"></a>
<a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
<a href="EVALUATION.md"><img alt="Status: experimental" src="https://img.shields.io/badge/status-experimental-orange.svg"></a>
</p>

<p><sub><strong>Hermes Blind by <a href="https://hermes-labs.ai">Hermes Labs</a></strong> — infrastructure for agents that act on real systems.</sub></p>

</div>

## The problem

Long coding-agent sessions can lose the shape of the request that started them.

As a Claude Code or Codex session grows, debugging output, tool results, intermediate decisions, and follow-up turns accumulate around the original instruction. The model may still have access to that history, but the user's initial constraints can become harder to keep salient.

When that happens, the usual recovery move is manual: scroll back, reconstruct what mattered, and restate it.

Hermes Blind makes that recovery deterministic.

It reads the first user turn from a supported local session transcript and generates a compact, inspectable recovery anchor that can be pasted or injected back into the session.

No summarizing model. No external service. No network request.

Hermes Blind also includes an evidence-bound prompt wrapper for LLM evaluation workflows. That is a secondary surface: the primary job is recovering original intent from long agent sessions.

## What it does

- **Find the latest supported session.** Discover a recent usable Claude Code or Codex JSONL log from supported local locations.
- **Recover the original user intent.** Parse the first real user turn while skipping tool output, sidechain/sub-agent turns, compaction summaries, and injected context.
- **Generate a compact anchor.** Produce Markdown that can be inspected before it is reintroduced to an agent.
- **Choose how much to recover.** Use `goals`, `first-sentence`, or `full` extraction modes depending on the context budget.
- **Work across agent hosts.** Install the portable skill/plugin surface in Claude Code, Codex CLI, or Gemini CLI.
- **Inject at a chosen turn.** Hermes Agent can call Blind through a `pre_llm_call` hook.
- **Wrap evaluation prompts.** Add explicit evidence and uncertainty constraints without calling a model.

## Quickstart

Hermes Blind requires Python 3.10+.

For an isolated command-line install:

```bash
pipx install hermes-blind
```

Or:

```bash
python -m pip install hermes-blind
```

From the project directory for an active Claude Code or Codex session:

```bash
hermes-blind apply   --latest   --format auto   --turn 9   --out recovery.md
```

Blind prints the session file it selected to stderr and writes an inspectable anchor to `recovery.md`.

A generated anchor looks like:

```markdown
# Recovery scaffold (anchor-extracted from turn 1, applied at turn 9)

## Original anchor
- stated_goal: "Ship the onboarding flow and verify the clean install"

## Session state
- session file: rollout.jsonl
- user turns observed: 9
```

Review the file, then provide it back to the agent or let a supported harness inject it at a chosen intervention point.

## Why this is different from summarization

Hermes Blind does not ask another model to reinterpret the request. It deterministically extracts what the user actually said in the initial turn, producing an anchor that is easy to inspect and reuse.

## Extraction modes

| Mode | Behavior | Use when |
|---|---|---|
| `goals` (default) | Preserves up to 12 goal-carrying sentences from the first user turn | Multi-step engineering tasks |
| `first-sentence` | Keeps the opening fragment, up to 240 characters | Very tight context budgets or simple prompts |
| `full` | Keeps up to 4,000 characters from the first prompt | The first prompt is already structured like a specification |

`--format auto` recognizes supported Claude Code and Codex JSONL shapes.

Blind skips records that are not the user's actual conversational turn, including supported forms of:

- tool results;
- sub-agent / sidechain turns;
- skill or slash-command expansions;
- compaction summaries;
- system reminders and task notifications;
- Codex environment context and injected `AGENTS.md` material.

The `--turn` value is a label for the recovery artifact. Blind does not automatically detect the correct intervention turn.

## Session discovery

`--latest` starts with Claude Code logs for the current project and scans local Codex rollouts, then chooses the newest usable log containing a user turn. If no Claude Code log matches and `--cwd` was not passed, the Claude search widens to other projects.

It honors:

- `CLAUDE_CONFIG_DIR`
- `CODEX_HOME`
- `--cwd PATH`

If discovery is ambiguous or nothing matches, Blind exits instead of silently guessing.

You can always provide the session file explicitly:

```bash
hermes-blind apply   --session /path/to/session.jsonl   --format auto   --turn 9   --out recovery.md
```

Generated recovery files can contain user-authored session text. Inspect them before sharing externally.

## Use it from an agent

A low-friction instruction to an agent is:

> Install `hermes-blind`, run `hermes-blind apply --latest --format auto --turn <current-turn-number> --out recovery.md`, show me the generated anchor, and use it to restate my original goals before continuing.

That keeps the recovery artifact visible rather than silently rewriting the conversation.

## Hermes Agent hook

Hermes Agent's `pre_llm_call` shell-hook contract can inject an anchor at a turn you choose:

```yaml
hooks:
  pre_llm_call:
    - command: "hermes-blind hermes-agent-hook --at-turn 9"
      timeout: 5
```

At the selected turn, Blind reads the hook payload from stdin and returns a compact context block.

The intervention point is chosen by the developer or harness. It is not an automatically detected drift event.

## Portable plugin / skill installation

The repository ships a portable plugin/skill surface for Claude Code, Codex CLI, and Gemini CLI.

### Claude Code

```bash
claude plugin marketplace add hermes-labs-ai/hermes-blind
claude plugin install hermes-blind@hermes-blind
```

### OpenAI Codex CLI

```bash
codex plugin marketplace add hermes-labs-ai/hermes-blind
codex plugin add hermes-blind@hermes-blind
```

### Gemini CLI

```bash
gemini extensions install https://github.com/hermes-labs-ai/hermes-blind --ref v0.3.2
```

Important boundary: **Gemini CLI can host the Hermes Blind skill, but Hermes Blind does not currently recover Gemini session logs.** From Gemini, the skill can operate on a Claude Code or Codex session you name.

For packaging details, see the [Claude marketplace manifest](.claude-plugin/marketplace.json), [Codex marketplace manifest](.agents/plugins/marketplace.json), [Gemini extension manifest](gemini-extension.json), and [Claude plugin notes](claude-plugin/README.md).

## Evidence-bound evaluation prompts

Hermes Blind can also wrap an evaluation prompt with explicit evidential constraints.

From the CLI:

```bash
hermes-blind apply   --variant v1   --prompt "Score this release from quoted evidence."
```

Output:

```text
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]

Score this release from quoted evidence.
```

Python API:

```python
from hermes_blind import wrap

prompt = wrap(
    "Rate this paper on novelty from 0 to 10 and cite the target text.",
    variant="v1",
)
```

Available variants include `null`, `micro`, `short`, `v1`, `full`, `placebo`, and `gate-only`.

The `null` variant is an exact no-op for controlled comparisons.

The wrapper formats text and makes no model call.

## Machine-readable evidence envelope

The same recovery extraction can be emitted in a machine-readable Hermes Reliability Lab result envelope:

```bash
python -m hermes_blind.evidence --session /path/to/session.jsonl --format auto
python -m hermes_blind.evidence --latest
```

The envelope adds observability around the same extraction: tool version, input hash, parsing findings, exit status, and other run metadata.

See [EVALUATION.md](EVALUATION.md) for implementation and evaluation details.

## Results

In a nine-session internal audit, the default goal-set anchor represented **40 of 66** pre-listed goals, compared with **7 of 66** for the earlier first-sentence heuristic. See [EVALUATION.md](EVALUATION.md) for the method and full results.

## Privacy

The core package is dependency-free at runtime, makes no model calls, and initiates no external network requests.

It reads the local session file selected by the caller or resolved through `--latest`.

Review generated recovery artifacts before sharing them outside the environment where the source session lives.

## Documentation

- [Evaluation and limitations](EVALUATION.md)
- [Intent and project framing](INTENT.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Citation metadata](CITATION.cff)
- [License](LICENSE)

## Part of the Hermes Labs toolkit

- [LintLang](https://github.com/hermes-labs-ai/lintlang) — Static analysis for AI agent tool descriptions and workflows.
- [Little Canary](https://github.com/hermes-labs-ai/little-canary) — Prompt injection detection through a powerless sacrificial model.
- [Fidelis](https://github.com/hermes-labs-ai/fidelis) — Semantic memory for long-running agents with local retrieval.
- [Hermeneutic](https://github.com/hermes-labs-ai/hermeneutic) — Reuse correction evidence and gate recurring epistemic drift.
- [zer0dex](https://github.com/hermes-labs-ai/zer0dex) — Local agent recall without burdening the context window.

## Project basics

Hermes Blind is maintained by [Hermes Labs](https://hermes-labs.ai).

MIT License. See [LICENSE](LICENSE).
