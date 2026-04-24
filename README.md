# hermes-blind

[![PyPI](https://img.shields.io/pypi/v/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-blind.svg)](https://pypi.org/project/hermes-blind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: experimental](https://img.shields.io/badge/status-experimental-orange.svg)](#status)

**The same eval prompt should not score 6.8 on one run and 8.4 on the next.** Context, memory, and knowledge of authorship bias the scorer. `hermes-blind` is a ~40-token language scaffold you prepend to any scoring or evaluation prompt to force the model to disclose prior exposure, score on quoted evidence only, and hedge on thin evidence.

It is a string. No model. No API. Backend-agnostic.

## Pain

- Same prompt, same target, different run → different score. No audit trail for which score is real.
- Claude scoring code it just wrote. The model knows. The score is inflated.
- CLAUDE.md, memory files, and session context leak into the rubric's judgment and the scorer optimizes to the owner's preferences instead of the target's evidence.
- You want a second opinion, but the second opinion is the same model that has the same context.
- `claude --bare` fixes this for the `claude-cli` backend only. Ollama, Sonnet-via-Bedrock, in-session scoring, and everyone else get nothing.

## Install

```bash
pip install hermes-blind
```

Python 3.10+. No dependencies beyond the standard library.

## Quickstart

```python
from hermes_blind import wrap

prompt = wrap("Rate this paper on novelty 0-10 with one sentence of rationale.")
# pass `prompt` to any backend: anthropic, openai, ollama, whatever
```

What `wrap()` produces:

```text
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]

Rate this paper on novelty 0-10 with one sentence of rationale.
```

Four mechanisms in that block:

1. **Disclosure ritual** — forcing the model to name its prior exposure in one line surfaces the bias to its own attention. Self-awareness of bias is a documented primary debiaser.
2. **Evidence-gate** — "only quoted evidence from the target" disqualifies claims drawn from the model's priors.
3. **Hedging license** — "unknown or thin evidence = hedge" removes the incentive to confabulate confident scores from memory.
4. **Output-shape discipline** (in the `full` variant) — keeps the model inside the expected output format, where context-bleed usually surfaces in sidebars and reasoning chains.

## Variants for ablation

```python
from hermes_blind import wrap, VARIANTS

for name in VARIANTS:
    print(name, "→", len(wrap("x", variant=name)))
```

| Variant | Tokens | Use case |
|---|---|---|
| `null` | 0 | Experimental control — the "without scaffold" baseline. |
| `micro` | ~8 | Minimum viable — is any debiasing effect detectable? |
| `short` | ~18 | Fits in tight token budgets. |
| `v1` | ~40 | **Default.** The full four-mechanism scaffold. |
| `full` | ~80 | Adds output-shape discipline + "prefer hedging over confident wrong". |

The `null` variant is a no-op (returns the prompt unchanged). It exists so an ablation harness can flip a variant name instead of branching the caller.

## Extracting the disclosure line

```python
from hermes_blind import extract_disclosure

response = model.complete(prompt).text
disclosure = extract_disclosure(response)
# disclosure is the string the model produced for "prior exposure", or None
```

A model that *never* discloses across many runs is a signal it's ignoring the scaffold. That's worth knowing; the empty result is itself data.

## Status

**v0.0.6 — experimental. Phase 2 of a 5-phase staged build.**

What is validated:

- The package installs, imports, and runs across Python 3.10-3.12.
- All five variants preserve the caller's prompt at the tail.
- Variants are length-ordered: `null < micro < short < v1 < full`.
- `extract_disclosure()` handles the common response shapes and rejects non-disclosure text.
- 19/19 unit tests pass (no LLM calls in the test suite; deterministic).

What is **not yet validated**:

- **Phase 4 empirical variance-reduction test has not been run.** The claim that this scaffold actually reduces score variance on repeated runs is a hypothesis, not a measurement. Do not treat this as a production debiaser until the ablation study ships. See `PLAN-v2.md` for the test protocol and pass/fail thresholds.
- Cross-model convergence (Opus, Sonnet, Haiku, Ollama qwen3.5) is a hypothesis too. Same Phase 4 test will measure it.

If Phase 4 shows no variance reduction, this package gets archived with a note. You have been warned.

## When to use it

- You are building an LLM-backed evaluator (rubric, code review, grading, classification) and you notice the same prompt scores differently across runs.
- You are invoking a model that has access to your CLAUDE.md / memory / session context, and you need that model to evaluate something authored within that same session without flattering you.
- You are running a multi-backend ablation and need the same debiaser string to work identically under Anthropic, OpenAI, and Ollama.

## When not to use it

- You need **guaranteed** bias elimination. This scaffold is statistical; individual runs may still be biased, and it does not defeat motivated adversarial contexts.
- You need **generation** debiasing. v0.0.x is tested only for scoring / evaluation.
- You are scoring long targets (>10k tokens) or multi-turn dialogues. Unvalidated in v0.0.x.
- You are running non-English prompts. Scaffold is English only.
- You already have `claude --bare` available and are scoring with claude-cli only. `--bare` is a stronger isolation primitive for that specific case. `hermes-blind` is complementary, not a substitute.

## How it relates to hermes-rubric

[`hermes-rubric`](https://github.com/hermes-labs-ai/hermes-rubric) enforces evidence-first discipline at the *tool* level — citations per dimension, hedging on thin evidence. That addresses fabrication but not bias in evidence *selection*. The scorer may still cherry-pick quotes consistent with a pre-formed conclusion drawn from session context.

`hermes-blind` addresses the selection stage: by forcing disclosure and gating on quoted evidence at the *prompt* level, the scaffold survives across backends that `hermes-rubric` will eventually support. Integration is gated on Phase 4 — if the empirical test fails, no integration happens.

## License

MIT. See [LICENSE](LICENSE).

---

Part of the [Hermes Labs](https://hermes-labs.ai) audit stack.
Companion tools: [hermes-rubric](https://github.com/hermes-labs-ai/hermes-rubric) · [hermes-seal](https://github.com/roli-lpci/hermes-seal) · [lintlang](https://github.com/hermes-labs-ai/lintlang) · [scaffold-lint](https://github.com/hermes-labs-ai/scaffold-lint)
