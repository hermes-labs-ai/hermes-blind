# Reliability Lab fixtures

Synthetic session logs authored for the Hermes Reliability Lab. None of them
came from a real Claude Code or Codex session; every line was written by hand
for this repository. They are used only to generate the lab's Hermes Blind
captures (`node scripts/capture-hermes-blind-fixture.mjs` in the site repo).
Not part of the package, not installed.

| File | Shape | What it exercises |
|---|---|---|
| `claude-first-turn.jsonl` | Claude Code project JSONL | valid first turn, three sentences; the third ("Keep ...") carries no listed goal verb and is reported, not kept |
| `codex-first-turn.jsonl` | Codex rollout JSONL | valid first turn recorded twice (event_msg + response_item), deduplicated; every sentence carries a listed goal verb |
| `claude-current-format.jsonl` | Claude Code project JSONL, v2.1.x shape | `ai-title` first line and full record metadata; the first user turn is followed by a tool result, an `isMeta` local-command caveat, `/status` and its `<local-command-stdout>`, a `/loop` command plus its `isMeta` skill expansion, a `<task-notification>`, an interruption marker, an `isSidechain` sub-agent turn, a `system` record, an `isCompactSummary` record naming a competing goal, and an image-plus-text turn; only turn 1, the two slash commands and the last turn are user turns |
| `claude-slash-command-first.jsonl` | Claude Code | the session opens with `/research <args>`; the anchor is the command as typed, not the `isMeta` skill expansion that follows |
| `codex-current-format.jsonl` | Codex rollout JSONL, current shape | `session_meta` and `turn_context` lines; injected `role: user` items (`<environment_context>`, `<user_instructions>` carrying a competing AGENTS.md instruction, `<turn_aborted>`) and a `developer` item precede and follow the two typed turns, each recorded as event_msg + response_item; reasoning, function-call, token-count and `compacted` records are ignored |
| `long-competing.jsonl` | Claude | 12 user turns; turn 7 gives competing instructions that must not replace turn 1 |
| `truncated.jsonl` | Claude | one corrupt line mid-file and a record cut off at the end |
| `missing-first-turn.jsonl` | Claude | only assistant records and text-less user records — no first turn to extract |
| `ambiguous-initial.jsonl` | Claude | two user turns before any assistant reply |
| `garbage.jsonl` | none | nothing parses |

Regenerate nothing by hand here; these are inputs, not outputs.
