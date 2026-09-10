---
name: hermes-blind
description: Recover the original goal of a long Claude Code or Codex session using the hermes-blind CLI. Trigger when the user asks what the original goal or ask was, wants the session re-anchored, or a long session seems to have drifted from its first turn.
---

Hermes Blind reads the first user turn from this session's local JSONL log
and writes a compact, inspectable recovery anchor. It is deterministic,
makes no model calls, and sends no network requests
(https://github.com/hermes-labs-ai/hermes-blind).

1. Pick a runner: if `hermes-blind --help` works, use the bare `hermes-blind`
   command below. Otherwise prefer `uvx hermes-blind` (zero-install, no PATH
   changes) over `pipx install hermes-blind` unless the user wants it
   installed persistently. Keep using whichever runner you picked for the
   rest of these steps — `uvx hermes-blind --help` alone does not put
   `hermes-blind` on PATH.
2. Find this session's local JSONL log (Claude Code: under
   `~/.claude/projects/`; Codex: under `~/.codex/sessions/`).
3. Run, substituting the real session path, current turn number, and the
   runner from step 1 (`hermes-blind ...` or `uvx hermes-blind ...`):
   ```
   hermes-blind apply --session <path> --format auto --turn <N> --out recovery.md
   ```
4. Show the generated `recovery.md` anchor to the user and use it to restate
   the original goal before continuing.

Constraints:
- Never overwrite an existing output file; only pass `--force` if the user
  explicitly asks to replace one. The input session file can never be used
  as the output path.
- The recovery file can contain user-authored text — treat it like any other
  local file and do not paste its contents anywhere the user has not asked
  for.
- `--turn` is a label, not a drift detector. Hermes Blind does not decide
  when recovery is needed and does not prove behavioral recovery — it only
  extracts the anchor once asked.
