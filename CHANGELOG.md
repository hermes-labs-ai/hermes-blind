# Changelog

All notable changes to `hermes-blind` will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/). The 0.x line remains experimental;
minor versions may change the public surface before 1.0.

## [Unreleased]

### Fixed
- The agent skill no longer dead-ends when the runner it pinned predates a flag
  it teaches. Both `SKILL.md` copies pin an exact release (`hermes-blind==0.2.0`
  on this branch) so an agent never fetches an unreviewed one, but step 2 teaches
  `apply --latest`, which did not exist before 0.3.0: an agent following the skill
  verbatim got `error: unrecognized arguments: --latest` and exit 2, and step 3's
  fallback only covered exit 1. Step 3 now covers any non-zero `--latest` run and
  names the older-pin case explicitly, so the agent falls back to `--session`
  instead of stopping. `tests/test_agent_skill.py` guards the pairing: a skill
  that teaches `--latest` must document that fallback.
- Claude Code session parsing now skips the records the current client
  (2.1.x) writes into the log that are not user turns: `isMeta` records
  (slash-command output, its caveat, skill expansions), `isSidechain`
  sub-agent records, `isCompactSummary` compaction summaries,
  `[Request interrupted by user]` markers, and text that is only injected
  context (`<system-reminder>`, `<task-notification>`, `<local-command-*>`,
  `<bash-std*>`, IDE context). A `/command args` record is kept as the
  command the user typed. Previously a turn-1 record that also carried a
  system reminder was either dropped whole (short) or anchored on the
  reminder text (long).
- Codex rollout parsing now skips the `role: user` items Codex persists for
  injected context (`<environment_context>`, `<user_instructions>` carrying
  AGENTS.md, `<turn_aborted>`, `<permissions instructions>`), which previously
  became turn 1. Typed `user_message` events are never filtered. `compacted`
  lines are recognized when sniffing the format, and a non-object first line
  no longer breaks sniffing.

### Added
- `hermes-blind apply --latest` finds this session's log instead of requiring
  the path, removing the hand lookup that was step 2 of the skill. It takes
  the most recently modified log that the existing parser finds a user turn
  in — so sub-agent-only logs are passed over — from
  `$CLAUDE_CONFIG_DIR/projects/` (default `~/.claude/projects/`) under the
  directory named after the current working directory with `/` replaced by
  `-`, or from `$CODEX_HOME/sessions/` (default `~/.codex/sessions/`)
  matching `**/rollout-*.jsonl`. `--cwd PATH` scopes the Claude Code search
  to another project directory; without it, a directory that has no log of
  its own widens the search to every project directory. The chosen file is
  printed to stderr. Nothing is guessed: no candidate, no candidate carrying
  a user turn, and two candidates sharing the newest modification time each
  exit 1 naming what was searched and what to pass instead. `--latest` and
  `--session` are mutually exclusive; `--session` is unchanged.
- `python -m hermes_blind.evidence` accepts the same `--latest` and `--cwd`.
  Discovery happens in the CLI: the emitter still reads only the one path it
  is handed, and still reports it by basename.
- Both `SKILL.md` copies now run `--latest` as the default path, with the
  manual `--session` lookup kept as the documented fallback.
- `fixtures/lab/claude-current-format.jsonl`, `claude-slash-command-first.jsonl`
  and `codex-current-format.jsonl`: hand-written fixtures in the current log
  shapes, with regression tests over the iterators, the scaffold and the
  evidence envelope.

### Evidence boundary

- `--latest` only chooses a path; extraction, rendering and every existing
  command are untouched, and no existing output changes. Discovery is tested
  against fake home directories built in `tmp_path`, not against a real
  machine's logs — the `/` → `-` project-directory encoding and the Codex
  `sessions/**/rollout-*.jsonl` layout are taken from the clients' documented
  behavior, and neither vendor documents those locations as stable. A second,
  punctuation-folded directory-name candidate is tried when the first does
  not exist, and a lookup that matches nothing refuses rather than widen past
  an explicit `--cwd`.
- This entry changes which records count as user turns; it does not change
  how the anchor is rendered from those turns, and the existing fixtures
  produce byte-identical output. Claude Code shapes were checked against
  logs written by Claude Code 2.1.268 and the client's own record markers;
  Codex shapes against the `openai/codex` rollout persistence policy and
  contextual-message filter at the time of writing. Neither vendor documents
  the log format as stable.

## [0.2.0] — 2026-09-07

### Added
- `python -m hermes_blind.evidence`: emit a recovery-anchor extraction as a Hermes Reliability Lab result envelope with the markdown scaffold embedded verbatim. Explicit `--session` only; writes nothing; reports the path by basename.
- `hermes_blind.apply.build_anchor()` returns an `AnchorResult` (the facts the scaffold is rendered from, plus the markdown); `build_recovery_scaffold_from_user_texts()` now delegates to it and its output is byte-identical.
- `hermes_blind.apply.ParseStats`: optional observability for the session iterators (lines read, unparseable lines, text-less user records skipped, user turns before the first assistant reply). The iterators yield exactly what they did before.

### Evidence boundary

- This release adds a new public API surface (`build_anchor`, `AnchorResult`,
  `ParseStats`, the `hermes_blind.evidence` module) without changing existing
  extraction semantics or output shapes; `build_anchor().markdown` remains
  byte-identical to `build_recovery_scaffold_from_user_texts()`. It reports
  parse observability — it does not detect drift, judge extraction quality,
  or establish that the envelope's findings correspond to model behavior.

## [0.1.5] — 2026-09-02

### Added

- Added an opt-in Hermes Agent `pre_llm_call` shell-hook adapter that injects
  a recovery anchor once at an explicitly selected turn.
- Added in-memory transcript extraction for hosts that already provide their
  conversation history, avoiding a temporary JSONL copy.

### Evidence boundary

- The integration uses Hermes Agent's ephemeral, fail-open context-injection
  contract. It does not detect drift, choose an intervention turn, or establish
  that reinserting the scaffold changes model behavior.

## [0.1.4] — 2026-08-04

### Changed

- Reframed the README around the two concrete user paths: recovering the
  original goal of a long Claude Code or Codex session, and adding evidence
  constraints to an evaluation prompt.
- Added direct `pipx` and `pip` installation paths, a copyable agent-led
  onboarding instruction, and clearer output and safety expectations.
- Improved PyPI keywords and project links for session recovery, agent tooling,
  and LLM evaluation discovery.
- Added multi-version CI with lint, tests, distribution checks, and isolated
  wheel-install smoke tests.
- Added credential-free PyPI publishing through GitHub Actions trusted
  publishing.

### Evidence boundary

- This release changes public presentation, packaging metadata, and release
  automation. It does not change runtime behavior or expand the behavioral
  claims established for 0.1.3.

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
