# Recovery-anchor fidelity evaluation

This is the public, privacy-safe report for the anchor-fidelity evidence cited
by hermes-blind 0.1.3. It covers one question only:

> When a long first user turn contains several goals, does the default
> `goals` recovery anchor represent more of those goals than the previous
> first-sentence anchor?

It does **not** evaluate the prompt-wrapping primitive, automatic drift
detection, downstream model adherence, or final task outcomes.

## What “recovery” means

Recovery is the package's second main surface, not a third mode. Given a
Claude Code or Codex JSONL session, `hermes-blind apply --session ...` reads
the first user turn and creates a markdown anchor that can be reviewed and
reinserted into a long session.

That recovery surface has three anchor modes:

- `goals` (default): extracts up to 12 goal-carrying sentences;
- `first-sentence`: retains the legacy compact anchor; and
- `full`: includes up to 4,000 characters of the first turn.

The package does not decide when to inject the anchor, inject it
automatically, or make a model call.

## Method

The design was frozen before corpus mining. Fresh-context model reviewers
were separated by role:

1. one reviewer saw only each turn-one mission seed and pre-listed its goals;
2. hermes-blind generated a legacy `first-sentence` anchor and a `goals`
   anchor for the same seed; and
3. a separate Haiku reviewer marked each pre-listed goal `REPRESENTED` or
   `ABSENT` in each anchor.

The evaluated extraction implementation was commit
`ca433597e8b3683d38dcd656fa7a35ad1c985114`.

The frozen plan called for 10 qualifying sessions. The completed receipt
contains 9 sessions and 66 goals, and does not record why the tenth session
was absent. The figures below use the observed denominator; no missing result
was imputed.

## Results

| Anchor | Goals represented | Coverage | Wilson 95% CI |
|---|---:|---:|---:|
| Legacy `first-sentence` | 7 / 66 | 10.6% | 5.2–20.3% |
| Default `goals` | 40 / 66 | 60.6% | 48.5–71.5% |

The default anchor represented 33 additional goals: a **50.0 percentage-point
increase** and **5.7×** the legacy coverage. At the paired goal level, all 7
goals represented by the legacy anchor remained represented; 33 previously
absent goals became represented; and none regressed.

Across sessions, `goals` improved coverage in 7 of 9 sessions and tied in 2.
An exploratory two-sided exact sign test over the 7 non-tied sessions gives
`p = 0.015625`. This test was calculated after the frozen evaluation rather
than pre-registered, and the sessions come from one private operating
environment, so it should be read as corroborating evidence rather than a
population-wide effect estimate.

The sanitized per-session counts and exact calculations are in
[`evaluation/anchor-fidelity-20260718/results.json`](evaluation/anchor-fidelity-20260718/results.json).

## What this establishes

For these nine long mission seeds, the 0.1.3 `goals` extractor preserved
substantially more of the original mission in the generated recovery artifact
than the legacy first-sentence heuristic. Mission representation is a
necessary first step for recovery: a goal absent from the artifact cannot be
restored by that artifact.

## What this does not establish

This evaluation does not show that reinserting the artifact makes a model
follow the mission, improves the final answer, prevents drift, or identifies
the right intervention time. Those are separate links in the causal chain and
need separate evaluations. The goal listing and representation judgments were
model-produced, not human-adjudicated, and the private corpus is too small and
too concentrated to support a general claim across users, languages, or
session types.

## Privacy and auditability

The source material consists of real private session openings that may contain
personal or unpublished project context. Raw text, local paths, complete
session identifiers, and individual judgments are therefore not published.
The public JSON contains only relabeled per-session counts, aggregate results,
method metadata, and SHA-256 commitments to the frozen internal receipts.

This protects the operator's private context, but it also means an outside
reader cannot independently audit the goal labels from this packet alone. A
future public or consented corpus is required for full external replication.

## Reproduce the public mechanics

The repository's synthetic fixtures are small, fabricated Claude Code and
Codex JSONL records—not sanitized private conversations. They verify the
reproducible software mechanics: parsing both log shapes, extracting multiple
goals, preserving a later goal after context-only prose, using safe markdown
fences, refusing unsafe overwrites, omitting parent paths from errors, and
deduplicating Codex's paired event shapes.

Run them with:

```bash
pytest -q tests/test_apply.py
```

These fixtures reproduce the mechanism and regression boundary. They do not
reproduce the private 40/66 behavioral audit.

## Receipt commitments

| Internal receipt | SHA-256 |
|---|---|
| Frozen specification | `05b4afc471eb47a15212fd3dbf225321ca61eeb698252b247594890ef3956555` |
| Source results | `376a5fbd69accb644171bac0f0363cca09e93d54f298f1adcc20ee4b9ca6fbcf` |
| Results report | `4774264dd9b8ea16b13fb63a2a81a73c240b68a9783b264c586e104173e92d2a` |
| Private corpus commitment file | `a241c04d94c572ae109e2e99f2e22e1c9cf3ae1df42c649010882685b8820c71` |
