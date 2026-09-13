"""Tests for hermes_blind.apply — the user-facing CLI entry point."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hermes_blind.apply import (
    build_recovery_scaffold,
    build_recovery_scaffold_from_user_texts,
    main,
)


def _write_session(tmp: Path, user_msgs: list[str]) -> Path:
    """Write a minimal Claude Code-shaped session JSONL with the given user texts."""
    p = tmp / "session.jsonl"
    lines = []
    for i, text in enumerate(user_msgs):
        lines.append(json.dumps({
            "type": "user",
            "message": {"content": text},
            "uuid": f"u{i}",
        }))
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": f"reply-{i}"}]},
            "uuid": f"a{i}",
        }))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_apply_wraps_prompt_with_default_variant(capsys):
    rc = main(["--prompt", "Score this paper"])
    assert rc == 0
    out = capsys.readouterr().out
    # v1 is the default and prepends a non-empty scaffold.
    assert out.endswith("Score this paper")
    assert len(out) > len("Score this paper")


def test_apply_null_variant_is_passthrough(capsys):
    rc = main(["--variant", "null", "--prompt", "exact text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "exact text"


def test_apply_reads_stdin_when_no_prompt(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
    rc = main(["--variant", "null"])
    assert rc == 0
    assert capsys.readouterr().out == "from stdin"


def test_apply_no_input_returns_2(capsys, monkeypatch):
    # Empty stdin and no --prompt and no --session -> usage error.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    rc = main([])
    assert rc == 2


def test_recovery_scaffold_extracts_first_user_turn_as_goal(tmp_path):
    session = _write_session(tmp_path, [
        "rewrite the auth flow to use OAuth 2.1 PKCE. tokens never logged.",
        "actually let's add v1 token deprecation",
        "and refactor the user model while we're at it",
    ])
    md = build_recovery_scaffold(session, turn=9)
    assert "Recovery scaffold" in md
    assert "applied at turn 9" in md
    assert "rewrite the auth flow to use OAuth 2.1 PKCE" in md
    assert "user turns observed: 3" in md
    assert "Reorient" in md
    assert "session file: session.jsonl" in md
    assert str(tmp_path) not in md


def test_recovery_scaffold_accepts_in_memory_host_transcript():
    md = build_recovery_scaffold_from_user_texts(
        ["Build the release and verify it.", "Continue."],
        turn=2,
        session_name="Hermes Agent conversation",
    )
    assert 'stated_goal: "Build the release and verify it"' in md
    assert "session source: Hermes Agent conversation" in md
    assert "user turns observed: 2" in md


def test_recovery_scaffold_missing_session_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_recovery_scaffold(tmp_path / "nope.jsonl", turn=9)


def test_recovery_scaffold_empty_session_raises(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        build_recovery_scaffold(p, turn=9)


def test_apply_session_writes_to_out(tmp_path, capsys):
    session = _write_session(tmp_path, ["original goal sentence"])
    out = tmp_path / "recovery.md"
    rc = main(["--session", str(session), "--turn", "5", "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    md = out.read_text(encoding="utf-8")
    assert "applied at turn 5" in md
    assert "original goal sentence" in md


def test_apply_session_refuses_to_overwrite_input(tmp_path, capsys):
    session = _write_session(tmp_path, ["original goal sentence"])
    original = session.read_bytes()
    rc = main(["--session", str(session), "--out", str(session)])
    assert rc == 2
    assert session.read_bytes() == original
    assert "must not replace" in capsys.readouterr().err


def test_apply_session_requires_force_for_existing_output(tmp_path, capsys):
    session = _write_session(tmp_path, ["original goal sentence"])
    out = tmp_path / "recovery.md"
    out.write_text("keep me", encoding="utf-8")

    assert main(["--session", str(session), "--out", str(out)]) == 2
    assert out.read_text(encoding="utf-8") == "keep me"
    assert "already exists" in capsys.readouterr().err

    assert main(["--session", str(session), "--out", str(out), "--force"]) == 0
    assert "original goal sentence" in out.read_text(encoding="utf-8")


def test_apply_session_emits_to_stdout_when_no_out(tmp_path, capsys):
    session = _write_session(tmp_path, ["goal text"])
    rc = main(["--session", str(session), "--turn", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "applied at turn 3" in out
    assert "goal text" in out


def test_apply_session_missing_returns_1(tmp_path):
    rc = main(["--session", str(tmp_path / "nope.jsonl")])
    assert rc == 1


def test_apply_session_error_redacts_parent_path(tmp_path, capsys):
    rc = main(["--session", str(tmp_path / "nope.jsonl")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nope.jsonl" in err
    assert str(tmp_path) not in err


# --- anchor-mode + codex-format additions (2026-07-18) ---

MULTI_GOAL_SEED = (
    "You are the mission session. Mine and audit recent work for receipts. "
    "Build a ship queue with named exits. Drain the decision backlog. "
    "Propose a canon index. The weather was nice yesterday. "
    "Verify every fact before it backs a decision."
)


def test_goals_mode_keeps_multi_goal_anchor(tmp_path):
    session = _write_session(tmp_path, [MULTI_GOAL_SEED, "next turn"])
    md = build_recovery_scaffold(session, turn=9)
    # Legacy stated_goal line still present (first sentence).
    assert 'stated_goal: "You are the mission session"' in md
    # Goal set captures the later goals the 240-char truncation dropped.
    assert "goal set (extracted from turn 1" in md
    assert "Build a ship queue with named exits" in md
    assert "Drain the decision backlog" in md
    assert "Verify every fact" in md
    # Non-goal filler is not in the goal set.
    assert "weather was nice" not in md


def test_first_sentence_mode_is_legacy_behavior(tmp_path):
    session = _write_session(tmp_path, [MULTI_GOAL_SEED])
    md = build_recovery_scaffold(session, turn=9, anchor_mode="first-sentence")
    assert "goal set" not in md
    assert "Drain the decision backlog" not in md


def test_full_mode_embeds_whole_turn(tmp_path):
    session = _write_session(tmp_path, [MULTI_GOAL_SEED])
    md = build_recovery_scaffold(session, turn=9, anchor_mode="full")
    assert "full turn-1 text:" in md
    assert "weather was nice" in md


def test_single_goal_seed_emits_no_goal_set(tmp_path):
    session = _write_session(tmp_path, ["fix the login bug"])
    md = build_recovery_scaffold(session, turn=9)
    assert "goal set" not in md


def test_context_first_seed_preserves_sole_later_goal(tmp_path):
    session = _write_session(
        tmp_path,
        ["Background: the auth service is flaky. Fix the login bug."],
    )
    md = build_recovery_scaffold(session, turn=9)
    assert 'stated_goal: "Background: the auth service is flaky"' in md
    assert "goal set (extracted from turn 1" in md
    assert "Fix the login bug." in md


def test_full_mode_uses_fence_longer_than_embedded_backticks(tmp_path):
    session = _write_session(
        tmp_path,
        ["Review this example:\n\n```python\nprint('ok')\n```\nThen ship it."],
    )
    md = build_recovery_scaffold(session, turn=9, anchor_mode="full")
    assert md.count("````") == 2
    assert "```python" in md
    assert "Then ship it." in md


def _write_codex_session(tmp: Path, user_msgs: list[str]) -> Path:
    p = tmp / "rollout.jsonl"
    lines = [json.dumps({"type": "session_meta", "payload": {"id": "x"}})]
    for text in user_msgs:
        lines.append(json.dumps({
            "type": "event_msg",
            "payload": {"type": "user_message", "message": text},
        }))
        lines.append(json.dumps({
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "ok"},
        }))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _response_item_user(text: str) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def test_codex_response_item_preserves_unpaired_initial_turn(tmp_path):
    p = tmp_path / "rollout-response-items.jsonl"
    first = "Build the initial release."
    second = "Verify the later patch."
    rows = [
        {"type": "session_meta", "payload": {"id": "x"}},
        _response_item_user(first),
        _response_item_user(second),
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": second},
        },
    ]
    p.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    md = build_recovery_scaffold(p, turn=3, fmt="codex")
    assert 'stated_goal: "Build the initial release"' in md
    assert "user turns observed: 2" in md


def test_codex_dedupe_keeps_legitimate_repeated_turn(tmp_path):
    p = tmp_path / "rollout-repeated.jsonl"
    text = "Retry the same request."
    rows = [
        _response_item_user(text),
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": text},
        },
        _response_item_user(text),
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": text},
        },
    ]
    p.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    md = build_recovery_scaffold(p, turn=3, fmt="codex")
    assert "user turns observed: 2" in md


def test_codex_format_parses_rollout(tmp_path):
    session = _write_codex_session(tmp_path, [MULTI_GOAL_SEED, "later turn"])
    md = build_recovery_scaffold(session, turn=5, fmt="codex")
    assert "user turns observed: 2" in md
    assert "Build a ship queue" in md


def test_auto_sniff_detects_codex(tmp_path):
    session = _write_codex_session(tmp_path, ["codex goal here"])
    md = build_recovery_scaffold(session, turn=5)
    assert "codex goal here" in md


def test_auto_sniff_detects_claude(tmp_path):
    session = _write_session(tmp_path, ["claude goal here"])
    md = build_recovery_scaffold(session, turn=5)
    assert "claude goal here" in md


def test_cli_anchor_mode_and_format_flags(tmp_path, capsys):
    session = _write_codex_session(tmp_path, [MULTI_GOAL_SEED])
    rc = main(["--session", str(session), "--turn", "4",
               "--anchor-mode", "full", "--format", "codex"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "full turn-1 text:" in out


# --- current Claude Code / Codex log shapes (2026-09-11) ---

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "lab"


def _write_rows(tmp: Path, name: str, rows: list[dict]) -> Path:
    p = tmp / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_claude_current_format_first_turn_skips_injected_records():
    from hermes_blind.apply import ParseStats, _iter_user_texts

    stats = ParseStats()
    turns = list(_iter_user_texts(FIXTURES / "claude-current-format.jsonl", stats))
    texts = [t for _, t in turns]
    assert texts[0].startswith("Ship the onboarding flow")
    # Slash commands are user turns, rendered as typed; the rest is not.
    assert texts == [
        texts[0],
        "/status",
        "/loop 5m check the installer job",
        "Use the existing fixtures where you can.",
    ]
    assert stats.user_turns == 4
    # tool result, caveat, command stdout, skill expansion, task notification,
    # interruption, sidechain turn, compaction summary.
    assert stats.skipped_user_records == 8
    assert stats.user_turns_before_first_assistant == 1
    md = build_recovery_scaffold(FIXTURES / "claude-current-format.jsonl", turn=9)
    assert 'stated_goal: "Ship the onboarding flow' in md
    assert "user turns observed: 4" in md
    assert "delete the old database" not in md  # the compaction summary's competing goal
    assert "Expanded skill body" not in md


def test_claude_session_opening_with_slash_command_anchors_on_the_command():
    md = build_recovery_scaffold(FIXTURES / "claude-slash-command-first.jsonl", turn=3)
    assert (
        'stated_goal: "/research Compare uv and pipx for the installer and propose one"'
        in md
    )
    assert "Expanded instructions" not in md
    assert "user turns observed: 2" in md


def test_claude_meta_sidechain_and_compact_summary_records_are_not_turns(tmp_path):
    rows = [
        {"type": "user", "isMeta": True, "message": {"content": "meta first"}},
        {"type": "user", "isSidechain": True, "message": {"content": "sub-agent prompt"}},
        {"type": "user", "isCompactSummary": True,
         "message": {"content": "This session is being continued. Summary: rewrite everything."}},
        {"type": "user", "message": {"content": "Fix the login bug."}},
    ]
    md = build_recovery_scaffold(_write_rows(tmp_path, "s.jsonl", rows), turn=2)
    assert 'stated_goal: "Fix the login bug"' in md
    assert "user turns observed: 1" in md


def test_claude_inline_system_reminder_is_stripped_not_dropped(tmp_path):
    """Older logs put the reminder in the same content list as the typed text.

    Before: a short record was dropped whole and a long one kept the reminder
    as the anchor. Now the reminder is removed and the typed text is the turn.
    """
    reminder = "<system-reminder>\nContents of CLAUDE.md: always run the tests.\n</system-reminder>"
    rows = [
        {"type": "user", "message": {"content": [
            {"type": "text", "text": reminder},
            {"type": "text", "text": "Ship the release."},
        ]}},
        {"type": "user", "message": {"content": [{"type": "text", "text": reminder}]}},
        {"type": "user", "message": {"content": reminder + "\nVerify it." + reminder * 20}},
    ]
    from hermes_blind.apply import ParseStats, _iter_user_texts

    stats = ParseStats()
    texts = [t for _, t in _iter_user_texts(_write_rows(tmp_path, "s.jsonl", rows), stats)]
    assert texts == ["Ship the release.", "Verify it."]
    assert stats.skipped_user_records == 1


def test_claude_interruption_markers_and_task_notifications_are_not_turns(tmp_path):
    rows = [
        {"type": "user", "message": {"content": "[Request interrupted by user for tool use]"}},
        {"type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
        {"type": "user", "message": {"content": "<task-notification>\n<task-id>x</task-id>\n<status>completed</status>\n</task-notification>"}},
        {"type": "user", "message": {"content": "Add the smoke test."}},
    ]
    md = build_recovery_scaffold(_write_rows(tmp_path, "s.jsonl", rows), turn=2)
    assert 'stated_goal: "Add the smoke test"' in md
    assert "user turns observed: 1" in md


def test_claude_plain_text_with_angle_brackets_is_untouched(tmp_path):
    text = "Render <b>bold</b> and keep <unknown-tag>this</unknown-tag> verbatim."
    rows = [{"type": "user", "message": {"content": text}}]
    from hermes_blind.apply import _iter_user_texts

    assert [t for _, t in _iter_user_texts(_write_rows(tmp_path, "s.jsonl", rows))] == [text]


def test_codex_current_format_skips_injected_context_items():
    from hermes_blind.apply import ParseStats, _iter_user_texts_codex

    stats = ParseStats()
    texts = [t for _, t in _iter_user_texts_codex(FIXTURES / "codex-current-format.jsonl", stats)]
    assert len(texts) == 2
    assert texts[0].startswith("Ship the onboarding flow")
    assert texts[1] == "Use the existing fixtures where you can."
    # environment_context, user_instructions, turn_aborted
    assert stats.skipped_user_records == 3
    assert stats.user_turns_before_first_assistant == 1
    md = build_recovery_scaffold(FIXTURES / "codex-current-format.jsonl", turn=9)
    assert "user turns observed: 2" in md
    assert "AGENTS.md" not in md
    assert "Delete the old database" not in md


def test_codex_legacy_rollout_without_event_msgs_still_skips_injected_items(tmp_path):
    rows = [
        {"type": "session_meta", "payload": {"id": "x"}},
        _response_item_user("<environment_context>\n<cwd>/tmp</cwd>\n</environment_context>"),
        _response_item_user("<user_instructions>\nRun everything twice.\n</user_instructions>"),
        _response_item_user("Build the initial release."),
    ]
    md = build_recovery_scaffold(_write_rows(tmp_path, "rollout.jsonl", rows), turn=3)
    assert 'stated_goal: "Build the initial release"' in md
    assert "user turns observed: 1" in md


def test_codex_event_msg_user_message_is_never_filtered(tmp_path):
    """Typed input that happens to start with a tag still counts when Codex
    recorded it as a user_message event."""
    rows = [
        {"type": "session_meta", "payload": {"id": "x"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": "<plan> ship it"}},
        _response_item_user("<plan> ship it"),
    ]
    md = build_recovery_scaffold(_write_rows(tmp_path, "rollout.jsonl", rows), turn=2)
    assert 'stated_goal: "<plan> ship it"' in md
    assert "user turns observed: 1" in md


def test_auto_sniff_handles_current_first_lines(tmp_path):
    from hermes_blind.apply import _sniff_format

    assert _sniff_format(FIXTURES / "claude-current-format.jsonl") == "claude"  # ai-title
    assert _sniff_format(FIXTURES / "codex-current-format.jsonl") == "codex"
    rows = [{"type": "compacted", "payload": {"message": "x"}}]
    assert _sniff_format(_write_rows(tmp_path, "c.jsonl", rows)) == "codex"
    p = tmp_path / "list-first.jsonl"
    p.write_text('[1, 2]\n{"type": "user", "message": {"content": "hi"}}\n', encoding="utf-8")
    assert _sniff_format(p) == "claude"
