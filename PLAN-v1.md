# hermes-blind — v1 design plan

## Problem

LLMs scoring a target inherit bias from four sources:

1. **Self-scoring bias** — LLM scoring its own authored work, rationalizes quality up.
2. **User-preference bias** — LLM has access to CLAUDE.md / memory / known owner
   preferences and optimizes scores toward what the owner wants to hear rather
   than what the evidence supports.
3. **Session-context carryover** — LLM inherits the conversation that produced
   the target, with commitment-consistency and motivated-reasoning effects.
4. **Prior-position commitment** — LLM defends earlier positions taken in the
   session, cannot score a contradiction neutrally.

`hermes-rubric` already enforces evidence-first discipline at the tool level
(citation required per dimension, hedging on thin evidence). That addresses
fabrication but NOT the four biases above, because the *evidence selection*
stage itself can be biased — the scorer may cherry-pick quotes consistent with
a pre-formed conclusion drawn from session context.

`claude --bare` mode fixes (2) and (3) for the `claude-cli` backend only by
stripping hooks, memory, and CLAUDE.md from the subprocess. It does nothing
for (1) or (4), nothing for other backends, and nothing for scoring calls
that happen in-session without subprocess isolation.

## Hypothesis

A short (~40-token) language scaffold, prepended to any scoring prompt, can
reduce all four biases by forcing:

- **Disclosure** of prior exposure (self-awareness of bias is a primary debiaser)
- **Evidence-gating** — only quoted text from the target is admissible
- **Hedging license** — "unknown or thin evidence = hedge" removes the
  incentive to confabulate confident scores from prior knowledge
- **Output-shape discipline** — answer only in the expected shape; no
  "reasoning" sidebar where context-bleed surfaces

This is LPCI-adjacent: Roli proved language scaffolds can carry state across
stateless inference. HERMES-BLIND is the *suppression dual* — a scaffold that
actively pushes state out rather than passing it through.

## Draft scaffold — HERMES-BLIND v1

```
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]
```

~40 tokens.

Shorter variant (~25 tokens):

```
[BLIND] Prior exposure? say so. Score on quoted evidence only. Thin = hedge. [/BLIND]
```

## Integration points

- `hermes-rubric` — prepend to every backend call in `backends.py`
- `rolitwin` — add as a fourth rule in the polished system prompt
- `/rolitwin`-style second-opinion tools
- Code review / PR review prompts
- `issue_harvester.py` extraction stage (Haiku inherits "candidate came from
  Claude's own session" knowledge; BLIND prevents that from coloring extraction)

## Success criteria (what makes this plan good)

A good v1 for hermes-blind should:

- Be **backend-agnostic** (works with Opus, Sonnet, Haiku, Ollama qwen3.5)
- Be **~40 tokens or less** (negligible per-call cost; wraps at scale)
- **Reduce score variance** on repeated runs of the same target by ≥30%
- **Improve cross-model score convergence** (std across backends ≤1.0 on a
  0-10 scale for the same target)
- **Not suppress signal** — a target that legitimately deserves a high score
  should still score high; BLIND should debias, not flatten
- **Be auditable** — the scaffold's effect should be visible in the disclosed
  "prior exposure" line so reviewers can inspect what the model "knew"
- **Be composable** — prepend as a string, no API changes needed
- **Be empirically validated** with a falsifiable test protocol, not just
  argued from first principles

## Known failure modes to design against

- **Scaffold ignored** — model treats it as boilerplate and proceeds with full
  context anyway. Mitigation: force a structural output ("state in one line")
  so non-compliance is visible.
- **Confession without compensation** — model discloses exposure but scores
  as-if biased anyway. Mitigation: evidence-gate makes prior-derived claims
  inadmissible independent of disclosure.
- **Over-hedging** — model hedges everything to avoid bias, compressing the
  score range and reducing signal. Mitigation: hedge only on thin evidence,
  not by default.
- **Scaffold contamination** — the scaffold itself contains cues about what
  the "right" answer is. Mitigation: scaffold must be intent-agnostic (no
  domain-specific language; works identically for any target).

## Out of scope for v1

- Fine-tuning a model to treat a single symbol (⊘) as "discard context"
- Multi-turn debiasing rituals
- Cross-lingual testing (v1 English only)
- Non-scoring tasks (classification, extraction — testable in v2)

## Test protocol (Phase 4 in the meta-plan)

1. Use the 4-paper `applied/` corpus in hermes-rubric as target set
2. Score each paper 5x with BLIND + 5x without, on each of {Opus, Sonnet, Haiku,
   qwen3.5:9b via Ollama}
3. Compute: within-model variance, across-model mean std, overall signal
   preservation (correlation with ground-truth ranking)
4. Pass if: variance reduction ≥30% AND cross-model std ≤1.0 AND signal
   correlation preserved within ±0.1

Total: 4 papers × 2 conditions × 5 runs × 4 models = 160 scoring runs.
At ~$0.05-0.08 per run = ~$8-13 total cost.
