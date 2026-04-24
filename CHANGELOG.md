# Changelog

All notable changes to `hermes-blind` will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/) — deliberate 0.0.x pre-1.0 range
signals experimental status until the Phase 4 empirical test passes.

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
