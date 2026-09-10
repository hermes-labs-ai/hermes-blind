---
name: hermes-blind
description: Recover the original goal of a long Claude Code or Codex session using the hermes-blind CLI. Trigger when the user asks what the original goal or ask was, wants the session re-anchored, or a long session seems to have drifted from its first turn.
---

Hermes Blind reads the first user turn from this session's local JSONL log
and writes a compact, inspectable recovery anchor. It is deterministic,
makes no model calls, and sends no network requests
(https://github.com/hermes-labs-ai/hermes-blind).

1. Confirm `hermes-blind` is available: run `hermes-blind --help`. If it is
   missing, use `uvx hermes-blind --help` (zero-install, no `pip install`
   needed) or `pipx install hermes-blind`.
2. Find this session's local JSONL log (Claude Code: under
   `~/.claude/projects/`; Codex: under `~/.codex/sessions/`).
3. Run, substituting the real session path and current turn number:
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
