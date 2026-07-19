# Changelog

All notable changes to `hermes-blind` will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/). The 0.x line remains experimental;
minor versions may change the public surface before 1.0.

## [0.1.3] — 2026-07-19

0.1.3 is the first public 0.1.x release. The public comparison is
**0.0.6 → 0.1.3**. Versions 0.1.0 through 0.1.2 were unpublished development
candidates.

### Added since public 0.0.6

- A dependency-free CLI: `hermes-blind apply`.
- Deterministic recovery-scaffold generation from Claude Code and Codex JSONL.
- `goals`, `first-sentence`, and `full` anchor modes.
- Intent-debias and target-scope preambles used by hermes-rubric.
- `placebo` and `gate-only` mechanism-isolation variants.

### Changed from the unpublished 0.1.2 candidate

- Goal-set extraction replaces first-sentence truncation as the default.
- Recovery output records the source filename instead of its absolute path.
- Recovery output refuses to overwrite its input and preserves existing output
  files unless `--force` is explicit.
- Public docs and metadata now separate tested mechanics from unproven
  behavioral efficacy.
- Added a privacy-safe anchor-fidelity report with sanitized per-session
  counts, statistical context, receipt commitments, and public synthetic
  mechanics fixtures; the report and sanitized data ship in the source
  distribution.
- The public CLI excludes unfinished experiment and analysis harnesses tied to
  sibling repositories.
- Removed the staged placeholder seal; it is not a release requirement.

### Evidence boundary

- A frozen 66-goal audit represented 40 pre-listed goals with goal-set
  extraction, versus 7 with the previous first-sentence heuristic: a 50.0
  percentage-point increase, with improvement in 7 of 9 sessions and ties in
  2. This supports substantially better mission representation in the
  recovery artifact.
- Bias reduction, downstream model adherence or task outcomes, automatic
  drift detection, and optimal timing remain unproven.

## [0.0.6] — 2026-04-24

### Added
- Initial release. Five scaffold variants (`null`, `micro`, `short`, `v1`, `full`)
  exposed via `wrap(prompt, variant)`.
- `extract_disclosure(response)` for parsing the model's disclosure line from
  a completed response.
- `token_estimate(variant)` rough token count per variant.
- 19 unit tests covering: variant correctness, caller-prompt preservation,
  length-ordering invariant, disclosure extraction (seven shapes incl. edge
  cases), scaffold structural invariants.
- `INTENT.md`, `PLAN-v1.md`, `PLAN-v2.md` — design trail.
- Three hermes-rubric audit runs on the plan under `rubric-runs/`:
  phase1-claude.json (5.4/10 on v1), phase1-v2.json (5.7/10 after iteration),
  phase3-adversarial.json (5.5/10 — low aggregate = useful adversarial
  signal; three real gaps surfaced: self-referential evaluation loop,
  length-vs-content confound, backend-generalization runtime check).

### Known not-yet-validated
- Empirical variance-reduction effect of the scaffold. Phase 4 ablation
  study not yet executed. Do not treat this release as a proven debiaser.
- Cross-model convergence across Opus / Sonnet / Haiku / Ollama qwen3.5.
- Behavior on long targets (>10k tokens) or multi-turn scoring.

### Not in this release
- CLI (library-only for v0.0.x)
- Integration into `hermes-rubric` backends (gated on Phase 4 pass)
- Non-English scaffold variants
