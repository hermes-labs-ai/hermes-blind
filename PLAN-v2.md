# hermes-blind — v2 design plan

> **Revision from v1:** addresses three hedged dimensions from the
> Phase 1 rubric audit (aggregate 5.4/10, backend=claude-cli-contextual):
> `Scaffold Minimality & Ablation Plan`, `Reproducibility Artifacts`,
> `Scope Honesty`. Also adds concrete novelty-justification and
> integration-feasibility sections for the two unnamed weak dimensions
> (scored 3/10 and 4/10 in Phase 1).

## Problem (unchanged from v1)

LLMs scoring a target inherit bias from four sources:

1. **Self-scoring bias** — scoring own authored work, rationalizes quality up.
2. **User-preference bias** — access to CLAUDE.md / memory / owner preferences
   shifts scores toward what the owner wants to hear.
3. **Session-context carryover** — conversation inherited from the target's
   production; commitment-consistency and motivated-reasoning effects.
4. **Prior-position commitment** — defends earlier positions in the session.

`hermes-rubric` enforces evidence-first discipline at the tool level (citations
per dimension, hedging on thin evidence). This addresses fabrication but NOT
the four biases above, because evidence *selection* can itself be biased.

`claude --bare` fixes (2) and (3) for `claude-cli` only, by stripping hooks,
memory, and CLAUDE.md from the subprocess. It does nothing for (1), (4), or
other backends.

## Hypothesis (unchanged)

A short (~40-token) language scaffold, prepended to any scoring prompt, can
reduce all four biases by forcing disclosure, evidence-gating, hedging
license, and output-shape discipline.

---

## Why a new tool (novelty justification — v2 addition)

**Why not just use `claude --bare`?** Backend-specific; only works when the
scorer is in a claude-cli subprocess. Fails for Ollama, in-session scoring,
or any other LLM backend. Scaffolds are backend-agnostic.

**Why not just trust hermes-rubric's evidence requirement?** Evidence *selection*
is biased by the same priors the rubric is trying to avoid. The scorer picks
quotes that confirm a pre-formed conclusion. BLIND addresses the selection
stage, not the citation stage.

**Why not just use a different model as reviewer?** Solves bias (1) but not
(2)-(4), and doesn't generalize. A scaffold generalizes; a model-swap requires
infrastructure change.

**Why a language scaffold specifically?** LPCI demonstrated scaffolds carry
state across stateless inference (Markov TE≈0, cross-model, measured
empirically). HERMES-BLIND tests the *suppression dual* — whether scaffolds
can actively push state out. If this works, it's a new primitive in the
scaffold-theory toolkit, not just a product.

## Draft scaffold — HERMES-BLIND v1

```
[HERMES-BLIND]
If you have prior exposure to this target or its author, state it in one line.
Score using only quoted evidence from the target text below.
Unknown or thin evidence = hedge; do not confabulate.
[/HERMES-BLIND]
```

~40 tokens.

---

## Ablation plan (addresses hedged dim: Scaffold Minimality)

Not two variants — a systematic length sweep. Five scaffold lengths tested
empirically to find the minimum-viable version:

| Variant | Tokens | Scaffold text |
|---|---|---|
| `blind-null` | 0 | (baseline — no scaffold) |
| `blind-micro` | ~8 | `[BLIND] Score on quoted evidence only. [/BLIND]` |
| `blind-short` | ~18 | `[BLIND] Prior exposure? disclose. Evidence quotes only. Thin=hedge. [/BLIND]` |
| `blind-v1` | ~40 | (the draft above) |
| `blind-full` | ~80 | v1 + "Do not reason outside the expected output shape" + "Defer to hedging over confident wrong scores" |

Each variant tested on all 4 papers × 5 runs × 4 backends = 80 runs per variant
= 400 runs total. Ablation identifies the point of diminishing returns —
the minimum token count at which bias-reduction saturates. Ship the shortest
variant that achieves the success criteria.

---

## Reproducibility artifacts (addresses hedged dim: Reproducibility)

**Test harness:** single Python script `tests/experiment_blind_ablation.py`.
Checked into the repo. Runs the full ablation with one command:

```bash
python -m hermes_blind.experiment --papers corpus/ --variants all --out results.json
```

**Fixture corpus:** the 4-paper `applied/` set from hermes-rubric, plus 2
adversarial targets (one deliberately weak paper, one high-quality paper) so
we can verify BLIND doesn't suppress legitimate signal. Fixture paths pinned
in `tests/fixtures.yaml` with sha256 hashes.

**Random seed policy:** each LLM call uses a fixed seed where the backend
supports it (Ollama yes, claude-cli no — claude's OpenAI/Anthropic backends
don't expose seed). For claude-cli runs, we report the per-run variance as a
band rather than claiming point reproducibility.

**Output format:** `results.json` with schema `{variant, paper, run, backend,
aggregate, hedge_dims, timestamp, cost_estimate}`. Computed derived metrics
written to `analysis.json`: within-variant variance, cross-backend std,
signal-preservation correlation against ground truth.

**Version pinning:** `pyproject.toml` pins `hermes-rubric>=0.1.1`. Experiment
log records `hermes-rubric.__version__` and the model identifier reported by
each backend (claude returns its model id; ollama returns the model tag).

**Model identifiers at time of v2 run:** Opus 4.7 (claude-opus-4-7), Sonnet
4.6 (claude-sonnet-4-6), Haiku 4.5 (claude-haiku-4-5-20251001), qwen3.5:9b.

---

## Success criteria — falsifiable pass/fail (unchanged scope, sharpened thresholds)

For `blind-v1` to ship as a working prototype:

1. **Variance reduction:** within-model variance on the same target across 5
   runs drops by ≥30% with scaffold vs. without. Measured as std dev of
   aggregate scores.
2. **Cross-model convergence:** std dev of aggregate scores across the four
   backends on the same target is ≤1.0 (on a 0-10 scale) with scaffold. Higher
   without.
3. **Signal preservation:** Spearman rank correlation between BLIND-scored
   rankings and no-BLIND rankings of the 6 papers is ≥0.7. If lower, BLIND is
   flattening signal, not debiasing.
4. **Scaffold observable effect:** for at least 20% of runs, the model's
   disclosed "prior exposure" line should be non-empty. If always empty, the
   model is ignoring the scaffold and we have no evidence it's affecting
   behavior.

If all four pass → ship. If any fail → iterate scaffold text, re-run ablation.

---

## Integration points (v2: more specific)

- **`hermes-rubric`** — `backends.py` line 74ish, prepend scaffold to the
  prompt arg before subprocess call. One-line change, gated by env var
  `HERMES_BLIND_ENABLED=1` for opt-in until validated.
- **`rolitwin`** — `twin_chat.py` `build_polished_system_prompt()` adds the
  scaffold as a final rule. Tests: existing 26 tests must still pass; add 2
  new tests for scaffold presence and disclosure line extraction.
- **`issue_harvester.py`** — extraction stage (`extract_candidates()`)
  prepends scaffold to the Haiku prompt. Prevents Haiku from inheriting
  "this candidate came from Claude's own session" knowledge when harvester
  is self-invoked.
- **`/rolitwin` Skill** — no change; the CLI-level integration in rolitwin
  covers it.
- **Ad-hoc usage** — `from hermes_blind import wrap; prompt = wrap(your_prompt)`.

---

## Scope honesty — what v1 does NOT do (v2: explicit)

**v1 does not:**
- Work on non-English prompts (scaffold is English-only; tested only in English)
- Defeat adversarial/jailbreak contexts (a sufficiently motivated session can
  override scaffold instructions; BLIND is for honest bias reduction, not
  adversarial robustness)
- Verify the scaffold was respected (we measure behavioral effect via score
  variance, not introspect the model's adherence)
- Work for generation tasks (v1 tested only for scoring/evaluation; generation
  bias is a different problem)
- Fine-tune any model (pure prompt-engineering; zero training data required)
- Replace `--bare` mode (complementary — use both when available)
- Guarantee zero bias (debiasing is statistical; individual runs may still be
  biased)
- Prevent fabrication (hermes-rubric's evidence citations do that; BLIND
  addresses a different bias layer)

**v1 is not validated for:**
- Long-target scoring (>10k tokens) — test corpus is 4 papers avg 2k tokens
- Multi-turn scoring dialogues — single-shot only
- Non-Anthropic / non-Qwen backends — v1 tests 4 backends, not all

**Known design limits:**
- Longer scaffolds cost more tokens at scale. `blind-v1` at ~40 tokens × 20
  calls/day × 365 days = ~290k tokens/year. Negligible but not zero.
- The "confession ritual" (disclose prior exposure) is honor-system; no way to
  enforce truthfulness of disclosure.
- Context-bleed through the CLI (non-bare) means the scaffold's effect is
  measured against a contaminated baseline. Phase 4 runs bare-mode too when
  API key is available to establish the true baseline.

---

## Known failure modes (from v1, kept)

- **Scaffold ignored** — mitigated by forcing structural output ("state in
  one line")
- **Confession without compensation** — mitigated by evidence-gate
- **Over-hedging** — mitigated by "thin evidence" qualifier (not "always hedge")
- **Scaffold contamination** — mitigated by intent-agnostic wording

---

## Test protocol — Phase 4 (unchanged)

1. Targets: 4-paper `applied/` corpus + 2 adversarial (weak + strong control)
   = 6 papers
2. Conditions: 5 variants (null, micro, short, v1, full) × with/without per
   variant is redundant since null = without; just run each variant once per
   run
3. Backends: Opus, Sonnet, Haiku, qwen3.5:9b
4. Runs: 5 per (variant, paper, backend)
5. Total: 6 × 5 × 4 × 5 = 600 scoring runs
6. Cost estimate: ~$25-40 (higher than v1 estimate; ablation adds 5× runs)
7. Wall time: ~4-6 hours with modest parallelism

If total cost exceeds $50, switch Haiku + Ollama to do the sweep and use Opus
only for the top-2 variants (reduces cost to ~$12-15).

---

## Out of scope for v1 (kept)

- Fine-tuning a model to treat a single symbol (⊘) as "discard context"
- Multi-turn debiasing rituals
- Cross-lingual testing (v1 English only)
- Non-scoring tasks (classification, extraction — testable in v2)
