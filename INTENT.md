# hermes-blind — Intent

A ~40-token language scaffold prepended to any scoring/evaluation prompt to
reduce context-bleed bias. Backend-agnostic. Complementary to `claude --bare`.

## Accepts

- prepends a versioned scaffold to the caller's prompt, unchanged at the tail
- forces the model to disclose prior exposure to the target or author in one
  line, making bias-contamination visible to downstream readers
- gates the model to use quoted evidence from the target only, disqualifying
  claims drawn from the model's own priors
- licenses hedging on thin evidence, removing the incentive to confabulate
  confident scores from memory
- exposes a `null` variant so ablation studies have a zero-token control with
  identical plumbing

## Rejects

- non-English scaffolds (v0.0.x is English only — translations untested)
- fine-tuning requirements (pure prompt-engineering; zero training data)
- replacement for `--bare` mode (complementary, not a substitute)
- generation-task debiasing (v0.0.x tested only for scoring / evaluation)
- guarantees of bias elimination (this is statistical debiasing; individual
  runs may still be biased)

## Non-goals (v0.0.x)

- A runtime enforcement layer (the scaffold is honor-system — see Phase 4
  empirical test for behavioral-effect measurement)
- Cross-lingual generalization
- Multi-turn debiasing rituals
- Integration into hermes-rubric until empirical variance-reduction is proven

## Design invariants

1. The `null` variant is a no-op — used as experimental control.
2. Variants are strictly length-ordered: `null < micro < short < v1 < full`.
3. The caller's prompt is preserved at the tail unchanged.
4. No dependency on external packages beyond the standard library.
5. `extract_disclosure()` only inspects the first 300 chars of a response —
   a model that buries "disclosure" deep in output is not disclosing.
