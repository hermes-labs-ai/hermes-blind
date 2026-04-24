# AGENTS.md — hermes-blind

Guidance for autonomous agents and LLM-tooling that may consume, extend, or integrate this package.

## What this is

A language scaffold — a string constant, nothing more — that wraps an LLM
scoring/evaluation prompt to force the model to (1) disclose prior exposure,
(2) score using quoted evidence from the target only, and (3) hedge on thin
evidence. It is **not** a model, an API, or a judge. It is a prompt prefix.

## What this is not

- Not a guaranteed debiaser. Effect size on real targets is **unmeasured in v0.0.x**.
- Not a replacement for `claude --bare` mode when that is available.
- Not an adversarial-robustness defense.
- Not a fine-tuning artifact (no training data).

## When to invoke

Use `wrap(prompt, variant="v1")` when:

- your agent is about to call an LLM for a scoring or evaluation task, AND
- the agent has, or may have, context-level knowledge about the target or its
  author that could bias the score (self-authored work, known preferences in
  a CLAUDE.md, memory files, session transcript)

Skip if:

- the task is generation, not scoring
- the target is >10k tokens (unvalidated)
- the backend you are calling is already in isolated `--bare` mode

## Minimal invocation

```python
from hermes_blind import wrap, extract_disclosure

# Wrap
prompt = wrap("Score this paper on novelty 0-10.", variant="v1")
response_text = your_model_call(prompt)

# Inspect the disclosure line (optional — useful for logging)
disclosure = extract_disclosure(response_text)
if disclosure:
    log("scaffold honored; model disclosed:", disclosure)
else:
    log("scaffold ignored or disclosure empty — treat score with suspicion")
```

## Expected output shape (from the model)

A cooperating model returns something like:

```
Prior exposure: I wrote an earlier draft of this paper in the current session.
Score: 6/10
Rationale: evidence cited at paragraphs 2 and 4 supports a mid-tier novelty
claim; paragraph 5's benchmark is uncorroborated.
```

The disclosure line is not required to be truthful — it is an honor-system
signal. A model that never discloses across many runs is ignoring the
scaffold, which is itself a useful observation.

## Known limitations

- **Scaffold ignored** — the model may treat the prefix as boilerplate and
  proceed with full-context reasoning. Mitigation is partial: the disclosure
  request forces structural output that makes non-compliance visible.
- **Confession without compensation** — the model discloses exposure but scores
  as-if biased anyway. Mitigation is the evidence-gate clause, which makes
  prior-derived claims inadmissible independent of disclosure.
- **Over-hedging** — hedge-licensing could flatten the score range. Mitigation
  is the "thin evidence" qualifier — hedge on thin, not by default.
- **Scaffold contamination** — the scaffold itself could cue "correct" answers.
  Mitigation is intent-agnostic wording (no domain terms, no target framing).

## Common failure modes

- `wrap(prompt, variant="ultra")` → `ValueError: Unknown variant: 'ultra'`.
  Only `null`, `micro`, `short`, `v1`, `full` are valid.
- `extract_disclosure(None)` → `None` (graceful; not an error).
- Caller's prompt disappeared? Check the tail of the wrapped string — the
  scaffold is a **prefix**, the caller's prompt is always at the end.

## Success signal

- Unit tests pass in your CI: `pytest` returns 0 across 19 tests, no skips.
- For empirical debiasing, success is a **≥30% reduction in score variance**
  on repeated runs with the scaffold vs. without, measured by Phase 4 of the
  staged build. Until that test runs and passes, treat v0.0.x as a hypothesis.

## Extension points

Future variants can be added to `VARIANTS` in `src/hermes_blind/scaffold.py`.
Any new variant must:

- Preserve the caller's prompt at the tail unchanged
- End with `\n\n` to separate scaffold from prompt
- Maintain the strict length ordering invariant (enforced by a test)
- Ship with a corresponding docstring update

Do not add dependencies. The stdlib-only guarantee is part of the tool's
shape and is enforced at review time.
