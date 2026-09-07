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
| `long-competing.jsonl` | Claude | 12 user turns; turn 7 gives competing instructions that must not replace turn 1 |
| `truncated.jsonl` | Claude | one corrupt line mid-file and a record cut off at the end |
| `missing-first-turn.jsonl` | Claude | only assistant records and text-less user records — no first turn to extract |
| `ambiguous-initial.jsonl` | Claude | two user turns before any assistant reply |
| `garbage.jsonl` | none | nothing parses |

Regenerate nothing by hand here; these are inputs, not outputs.
