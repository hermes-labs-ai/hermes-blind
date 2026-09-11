"""hermes-blind apply — user-facing entry point.

Two modes:

1. Wrap a prompt with a scaffold variant (read prompt from --prompt or stdin):

       hermes-blind apply --variant v1 --prompt "Score this paper"
       echo "Score this paper" | hermes-blind apply --variant short

   Emits the scaffold-prepended prompt to stdout. This is the primitive
   the experiment harness uses internally; exposing it as a CLI lets you
   apply the same scaffold variant to any prompt outside the harness.

2. Build a recovery scaffold for a Claude Code or Codex session JSONL:

       hermes-blind apply --session ~/.claude/projects/<id>.jsonl \\
                          --turn 9 --out recovered.md

   Reads the session JSONL, extracts goal-carrying sentences from the first
   user turn, and emits a markdown recovery block. Deterministic — no model
   or network call. The output can contain user text; inspect it before
   sharing.

The two modes are mutually exclusive; mode 1 is the default.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from hermes_blind.scaffold import VARIANTS, wrap


@dataclass
class ParseStats:
    """What the parser saw while reading a session log.

    Purely observational: the iterators behave identically whether or not a
    ParseStats is passed. It exists so a caller can report, rather than guess,
    how much of a file parsed and whether the first turn was unambiguous.
    """

    lines: int = 0
    unparseable_lines: int = 0
    skipped_user_records: int = 0
    user_turns: int = 0
    user_turns_before_first_assistant: int = 0
    _seen_assistant: bool = field(default=False, repr=False)

    def _user_turn(self) -> None:
        self.user_turns += 1
        if not self._seen_assistant:
            self.user_turns_before_first_assistant += 1


# Claude Code wraps text it injects into user records in these tags: system
# reminders, background-task notifications, `!` shell output, `/command`
# stdout and its caveat, IDE context. They are not the user's words.
_CLAUDE_INJECTED_TAG_RE = re.compile(
    r"<(system-reminder|task-notification|local-command-stdout|local-command-stderr|"
    r"local-command-caveat|bash-stdout|bash-stderr|ide_opened_file|ide_selection)"
    r"(?:\s[^>]*)?>.*?</\1>\s*",
    re.DOTALL,
)
# A slash command is logged as <command-name>/x</command-name>
# <command-message>x</command-message> <command-args>…</command-args>.
_CLAUDE_COMMAND_TAG_RE = re.compile(
    r"<(command-name|command-message|command-args)(?:\s[^>]*)?>(.*?)</\1>\s*", re.DOTALL
)
_CLAUDE_INTERRUPTED_TEXTS = frozenset({
    "[Request interrupted by user]",
    "[Request interrupted by user for tool use]",
})


def _claude_user_text(obj: dict) -> str | None:
    """The user-authored text of a Claude Code ``type: user`` record, or None.

    None means the record is not a user turn: a tool result, a sidechain
    (sub-agent) record, a meta record (slash-command output, its caveat,
    skill expansions), a compaction summary, an interruption marker, or a
    record that carries only injected context. A slash command is rendered as
    the ``/name args`` the user typed. Text without any injected tag is
    returned exactly as recorded.
    """
    if obj.get("isMeta") or obj.get("isSidechain") or obj.get("isCompactSummary"):
        return None
    content = obj.get("message", {}).get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [
            p.get("text", "") for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        text = "\n".join(p for p in parts if p)
    if "<" in text:
        text = _CLAUDE_INJECTED_TAG_RE.sub("", text)
        command: dict[str, str] = {}
        def _take(match: re.Match[str]) -> str:
            command[match.group(1)] = match.group(2).strip()
            return ""
        rest = _CLAUDE_COMMAND_TAG_RE.sub(_take, text)
        if "command-name" in command:
            head = " ".join(
                s for s in (command["command-name"], command.get("command-args", "")) if s
            )
            text = head + ("\n" + rest.strip() if rest.strip() else "")
    if not text.strip() or text.strip() in _CLAUDE_INTERRUPTED_TEXTS:
        return None
    return text


def _iter_user_texts(
    jsonl_path: Path, stats: ParseStats | None = None
) -> Iterator[tuple[int, str]]:
    """Yield (turn_index, user_message_text) for each user turn in a Claude Code
    session JSONL (~/.claude/projects/<project>/<session>.jsonl).

    Only ``type: user`` records count; see :func:`_claude_user_text` for which
    of those are user turns. Turn index is 1-based and counts only real user
    turns (not tool results or injected records).
    """
    n = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if stats is not None:
                stats.lines += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if stats is not None:
                    stats.unparseable_lines += 1
                continue
            if not isinstance(obj, dict):
                if stats is not None:
                    stats.unparseable_lines += 1
                continue
            if obj.get("type") == "assistant" and stats is not None:
                if not obj.get("isSidechain"):
                    stats._seen_assistant = True
            if obj.get("type") != "user":
                continue
            text = _claude_user_text(obj)
            if text is None:
                if stats is not None:
                    stats.skipped_user_records += 1
                continue
            n += 1
            if stats is not None:
                stats._user_turn()
            yield n, text


def _iter_user_texts_codex(
    jsonl_path: Path, stats: ParseStats | None = None
) -> Iterator[tuple[int, str]]:
    """Yield (turn_index, user_message_text) for each user turn in a Codex
    rollout JSONL (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl).

    Codex can record a user turn as a response_item message, an
    event_msg/user_message, or both. When both adjacent extracted records
    carry identical text, yield the turn once.

    Codex also persists the context it injects into the model's input as
    ``role: user`` response_items — ``<environment_context>``,
    ``<user_instructions>`` (AGENTS.md), ``<turn_aborted>`` and similar.
    Those are skipped by their leading tag. An event_msg/user_message only
    ever carries typed input, so it is never filtered.
    """
    n = 0
    previous_text: str | None = None
    previous_shape: str | None = None
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if stats is not None:
                stats.lines += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if stats is not None:
                    stats.unparseable_lines += 1
                continue
            if not isinstance(obj, dict):
                if stats is not None:
                    stats.unparseable_lines += 1
                continue
            top_type = obj.get("type")
            payload = obj.get("payload") or {}
            if (
                stats is not None
                and top_type == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") == "assistant"
            ):
                stats._seen_assistant = True
            text = ""
            shape = ""
            if top_type == "event_msg" and payload.get("type") == "user_message":
                text = payload.get("message") or ""
                shape = "event_msg"
            elif (
                top_type == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") == "user"
            ):
                content = payload.get("content") or []
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "\n".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict)
                        and part.get("type") in {"input_text", "text"}
                        and isinstance(part.get("text"), str)
                    )
                shape = "response_item"
                if isinstance(text, str) and _CODEX_INJECTED_PREFIX_RE.match(text):
                    text = ""
            if not isinstance(text, str) or not text.strip():
                if stats is not None and shape:
                    stats.skipped_user_records += 1
                continue
            if text == previous_text and shape != previous_shape:
                continue
            n += 1
            if stats is not None:
                stats._user_turn()
            previous_text = text
            previous_shape = shape
            yield n, text


# Codex writes injected context as a user message that opens with a snake_case
# tag (``<environment_context>``, ``<user_instructions>``, ``<turn_aborted>``,
# ``<permissions instructions>``). Typed input is never wrapped this way.
_CODEX_INJECTED_PREFIX_RE = re.compile(r"\s*<[a-z][a-z0-9_]*(?: [a-z0-9_]+)*>")

_CODEX_TOP_TYPES = {"session_meta", "turn_context", "event_msg",
                    "response_item", "compacted", "world_state"}


def _sniff_format(jsonl_path: Path) -> str:
    """Return 'codex' or 'claude' by inspecting the first parseable line."""
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if obj.get("type") in _CODEX_TOP_TYPES:
                return "codex"
            return "claude"
    return "claude"


# Verbs that mark a sentence as goal-carrying in a mission seed. Broad on
# purpose: this extracts the anchor, it does not detect drift — a spurious
# extra sentence costs a line of scaffold, a dropped goal loses the anchor.
_GOAL_VERB_RE = re.compile(
    r"\b(build|ship|close|drain|audit|propose|integrat|verify|draft|align|"
    r"appl(?:y|ied)|mine|fix|run|eval(?:uate)?|write|creat|design|test|"
    r"review|publish|prepar|ensur|make|add|refactor|deploy|measur|"
    r"synthesi[sz]e|pick|consolidat|research|adopt|check|land|score|"
    r"board|need to|we need|let'?s|goal|mission|deliverable)\w*\b",
    re.IGNORECASE,
)

# Split on sentence enders (incl. across a line wrap) and paragraph breaks —
# NOT on single newlines, so hard-wrapped dictated prose stays whole.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}|(?<=[;:])\n")

_MAX_GOALS = 12
_MAX_GOAL_CHARS = 220
_MAX_FULL_CHARS = 4000


def _split_sentences(text: str) -> list[str]:
    """Split turn-1 text into normalized sentences (the goal filter's input)."""
    return [
        re.sub(r"\s+", " ", s).strip()
        for s in _SENT_SPLIT_RE.split(text) if s and s.strip()
    ]


def _extract_goal_sentences(text: str) -> tuple[list[str], int]:
    """Split turn-1 text into sentences and keep the goal-carrying ones.

    Returns (kept_goal_sentences, total_goal_sentence_count).
    """
    sentences = _split_sentences(text)
    goals = [s for s in sentences if _GOAL_VERB_RE.search(s)]
    return [g[:_MAX_GOAL_CHARS] for g in goals[:_MAX_GOALS]], len(goals)


def unmatched_sentences(text: str) -> list[str]:
    """Sentences of turn-1 text that carry no goal verb and so never enter the goal set.

    Observational only. The goal-verb list is finite and broad on purpose; this
    reports what fell outside it so a reader can judge, instead of guessing
    from what was kept.
    """
    return [s for s in _split_sentences(text) if not _GOAL_VERB_RE.search(s)]


def build_recovery_scaffold(
    jsonl_path: Path,
    turn: int,
    anchor_mode: str = "goals",
    fmt: str = "auto",
) -> str:
    """Build a markdown recovery scaffold from a session JSONL.

    Extracts:
      - stated_goal: first user turn text (first sentence or 240 chars)
      - goal set (anchor_mode="goals", default): every goal-carrying sentence
        of turn 1, so dictated multi-goal missions are not truncated to a
        fragment (fixes the 2026-07-17 anchor-truncation finding)
      - full anchor (anchor_mode="full"): the entire turn-1 text, capped
      - applied_at_turn: the turn requested by the caller

    ``fmt`` selects the session log dialect: "claude" (Claude Code project
    JSONL), "codex" (Codex rollout JSONL), or "auto" (sniff first line).

    Emits a scaffold compatible with the v1 anchor-template — the next turn
    can prepend this block to re-anchor on the original intent.
    """
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"session jsonl not found: {jsonl_path.name}")
    if fmt == "auto":
        fmt = _sniff_format(jsonl_path)
    iterator = (_iter_user_texts_codex if fmt == "codex"
                else _iter_user_texts)
    user_turns = list(iterator(jsonl_path))
    if not user_turns:
        raise ValueError(f"no user turns found in {jsonl_path.name}")
    return build_recovery_scaffold_from_user_texts(
        [text for _, text in user_turns],
        turn,
        anchor_mode=anchor_mode,
        session_name=jsonl_path.name,
        session_label="session file",
    )


@dataclass
class AnchorResult:
    """The facts a recovery scaffold is rendered from, plus the rendered markdown.

    Every field is something the markdown already states; this only makes it
    addressable without parsing the markdown back. ``markdown`` is byte for
    byte what :func:`build_recovery_scaffold_from_user_texts` returns.
    """

    stated_goal: str
    anchor_mode: str
    additional_goals: list[str]
    goal_sentences_total: int
    sentences_total: int
    unmatched_sentences: list[str]
    first_turn_chars: int
    full_truncated: bool
    user_turns: int
    turn: int
    session_name: str
    markdown: str


def build_recovery_scaffold_from_user_texts(
    user_texts: list[str],
    turn: int,
    *,
    anchor_mode: str = "goals",
    session_name: str = "session",
    session_label: str = "session source",
) -> str:
    """Build a recovery scaffold from an in-memory sequence of user turns.

    This is the host-integration counterpart to :func:`build_recovery_scaffold`:
    callers that already receive a conversation transcript do not need to
    serialize private session text to a temporary file merely to use Blind's
    deterministic anchor extraction.
    """
    return build_anchor(
        user_texts,
        turn,
        anchor_mode=anchor_mode,
        session_name=session_name,
        session_label=session_label,
    ).markdown


def build_anchor(
    user_texts: list[str],
    turn: int,
    *,
    anchor_mode: str = "goals",
    session_name: str = "session",
    session_label: str = "session source",
) -> AnchorResult:
    """Extract the turn-1 anchor and render it; the structured twin of
    :func:`build_recovery_scaffold_from_user_texts` with identical output."""
    user_texts = [text for text in user_texts if isinstance(text, str) and text.strip()]
    if not user_texts:
        raise ValueError("no user turns found in session")

    first = user_texts[0].strip()
    # First sentence, capped at 240 chars.
    end = min(
        (i for i in (first.find(". "), first.find("\n\n"), 240) if i > 0),
        default=240,
    )
    stated_goal = first[:end].strip().rstrip(".")

    total_user_turns = len(user_texts)
    anchor_lines = [f'- stated_goal: "{stated_goal}"']
    additional: list[str] = []
    total = 0
    full_truncated = False
    if anchor_mode == "goals":
        kept, total = _extract_goal_sentences(first)
        # Emit only goals that add information beyond stated_goal. This keeps
        # the compact single-goal case deduplicated while preserving a sole
        # goal that follows a context-only opening sentence.
        stated_folded = stated_goal.casefold()
        additional = [
            goal
            for goal in kept
            if goal.rstrip(".!?").casefold() not in stated_folded
            and stated_folded not in goal.casefold()
        ]
        if additional:
            anchor_lines.append(
                f"- goal set (extracted from turn 1, "
                f"{len(additional)} additional of {total} goal sentences):"
            )
            anchor_lines.extend(
                f"  {i}. {g}" for i, g in enumerate(additional, 1)
            )
    elif anchor_mode == "full":
        full = first[:_MAX_FULL_CHARS]
        full_truncated = len(first) > _MAX_FULL_CHARS
        suffix = " …[truncated]" if full_truncated else ""
        longest_backtick_run = max(
            (len(match.group(0)) for match in re.finditer(r"`+", full)),
            default=0,
        )
        fence = "`" * max(3, longest_backtick_run + 1)
        anchor_lines.append("- full turn-1 text:")
        anchor_lines.append("")
        anchor_lines.append(fence)
        anchor_lines.append(full + suffix)
        anchor_lines.append(fence)

    lines = [
        f"# Recovery scaffold (anchor-extracted from turn 1, applied at turn {turn})",
        "",
        "## Original anchor",
        *anchor_lines,
        "",
        "## Session state",
        f"- {session_label}: {session_name}",
        f"- user turns observed: {total_user_turns}",
        f"- recovery applied at turn: {turn}",
        "",
        "## Reorient",
        "The user's stated goal at turn 1 is the load-bearing anchor. Re-read it",
        "before continuing. If the trajectory diverged from the original intent",
        "across intervening turns, hold the original goal as primary; treat any",
        "new directives as scoped sub-tasks unless the user has explicitly revised",
        "the goal.",
    ]
    return AnchorResult(
        stated_goal=stated_goal,
        anchor_mode=anchor_mode,
        additional_goals=additional,
        goal_sentences_total=total,
        sentences_total=len(_split_sentences(first)),
        unmatched_sentences=unmatched_sentences(first),
        first_turn_chars=len(first),
        full_truncated=full_truncated,
        user_turns=total_user_turns,
        turn=turn,
        session_name=session_name,
        markdown="\n".join(lines) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hermes-blind apply",
        description="Apply a hermes-blind scaffold to a prompt, or build a "
                    "recovery scaffold from Claude Code or Codex session JSONL.",
    )
    p.add_argument(
        "--variant", default="v1",
        choices=sorted(VARIANTS.keys()),
        help="Scaffold variant to apply (mode 1). Default: v1.",
    )
    p.add_argument(
        "--prompt",
        help="Prompt text to wrap (mode 1). If absent, reads from stdin.",
    )
    p.add_argument(
        "--session",
        help="Path to a Claude Code or Codex session JSONL (recovery mode).",
    )
    p.add_argument(
        "--turn", type=int, default=9,
        help="Metadata label for the intended recovery turn. Default: 9; "
             "this is not an automatic trigger or efficacy threshold.",
    )
    p.add_argument(
        "--out",
        help="Output path for the recovery scaffold markdown (mode 2). "
             "Default: stdout.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Allow recovery mode to replace an existing output file. The "
             "input session file can never be replaced.",
    )
    p.add_argument(
        "--anchor-mode", default="goals",
        choices=("first-sentence", "goals", "full"),
        help="Anchor extraction mode (mode 2). 'goals' (default) keeps every "
             "goal-carrying sentence of turn 1 so dictated multi-goal "
             "missions are not truncated; 'first-sentence' is the legacy "
             "240-char behavior; 'full' embeds the whole turn-1 text.",
    )
    p.add_argument(
        "--format", default="auto", dest="fmt",
        choices=("auto", "claude", "codex"),
        help="Session JSONL dialect (mode 2). 'auto' (default) sniffs the "
             "file; 'codex' parses ~/.codex/sessions rollout files.",
    )
    args = p.parse_args(argv)

    if args.session:
        try:
            md = build_recovery_scaffold(
                Path(args.session).expanduser(), args.turn,
                anchor_mode=args.anchor_mode, fmt=args.fmt,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"hermes-blind apply: {e}", file=sys.stderr)
            return 1
        if args.out:
            session_path = Path(args.session).expanduser().resolve()
            out_path = Path(args.out).expanduser()
            if out_path.resolve() == session_path:
                print(
                    "hermes-blind apply: output must not replace the input "
                    f"session file: {out_path.name}",
                    file=sys.stderr,
                )
                return 2
            if out_path.exists() and not args.force:
                print(
                    "hermes-blind apply: output already exists; pass --force "
                    f"to replace it: {out_path.name}",
                    file=sys.stderr,
                )
                return 2
            out_path.write_text(md, encoding="utf-8")
            print(f"wrote {args.out}", file=sys.stderr)
        else:
            sys.stdout.write(md)
        return 0

    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    if not prompt:
        print("hermes-blind apply: no prompt provided "
              "(use --prompt, stdin, or --session)", file=sys.stderr)
        return 2
    sys.stdout.write(wrap(prompt, variant=args.variant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
