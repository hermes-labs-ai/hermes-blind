"""Reliability Lab envelope contract for hermes-blind: explicit paths only, nothing written."""

from __future__ import annotations

import builtins
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_blind import __version__, evidence
from hermes_blind.apply import ParseStats, build_anchor, build_recovery_scaffold
from hermes_blind.evidence import envelope_for

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "fixtures" / "lab"


def _ids(result: dict) -> list[str]:
    return [f["id"] for f in result["findings"]]


def _finding(result: dict, identifier: str) -> dict:
    return next(f for f in result["findings"] if f["id"] == identifier)


# --- the refactor changes nothing -----------------------------------------


@pytest.mark.parametrize("name", ["claude-first-turn.jsonl", "codex-first-turn.jsonl", "long-competing.jsonl"])
@pytest.mark.parametrize("anchor_mode", ["goals", "first-sentence", "full"])
def test_structured_anchor_renders_byte_identical_markdown(name, anchor_mode) -> None:
    path = FIXTURES / name
    via_scaffold = build_recovery_scaffold(path, 9, anchor_mode=anchor_mode, fmt="auto")
    via_envelope = envelope_for(path, anchor_mode=anchor_mode)["data"]["markdown"]
    assert via_envelope == via_scaffold


def test_parse_stats_do_not_change_what_the_iterators_yield() -> None:
    from hermes_blind.apply import _iter_user_texts, _iter_user_texts_codex

    for name, iterator in (
        ("claude-first-turn.jsonl", _iter_user_texts),
        ("truncated.jsonl", _iter_user_texts),
        ("codex-first-turn.jsonl", _iter_user_texts_codex),
    ):
        plain = list(iterator(FIXTURES / name))
        with_stats = list(iterator(FIXTURES / name, ParseStats()))
        assert plain == with_stats, name


# --- canonical cases -------------------------------------------------------


def test_claude_first_turn_is_extracted_with_its_goal_set() -> None:
    result = envelope_for(FIXTURES / "claude-first-turn.jsonl")
    assert result["envelope"] == "hermes.reliability-lab.result/1"
    assert result["tool"] == "hermes-blind"
    assert result["toolVersion"] == __version__
    assert result["command"] == "apply"
    assert result["mode"] == "executed"
    assert result["status"] == "warn" == evidence.worst_status(result["findings"])
    assert result["exitCode"] == 0
    assert result["data"]["format"] == {"requested": "auto", "detected": "claude"}
    assert result["data"]["stats"]["userTurns"] == 2
    anchor = result["data"]["anchor"]
    assert anchor["statedGoal"] == "Ship the onboarding flow for the demo tenant and verify the clean install on a fresh machine"
    # "Keep ..." carries no verb from the product's goal-verb list: reported, not kept.
    assert anchor["additionalGoals"] == ["Add a smoke test that runs the installer end to end."]
    assert anchor["goalSentencesTotal"] == 2
    assert anchor["sentencesTotal"] == 3
    assert anchor["unmatchedSentences"] == ["Keep the public catalog boundary unchanged."]
    assert "## Original anchor" in result["data"]["markdown"]
    assert "Keep the public catalog boundary" not in result["data"]["markdown"]
    assert _finding(result, "anchor.goal-set")["summary"].startswith("1 additional of 2")
    unmatched = _finding(result, "anchor.unmatched-sentences")
    assert unmatched["severity"] == "warn"
    assert "Keep the public catalog boundary unchanged." in unmatched["detail"]
    assert result["data"]["readPaths"] == ["claude-first-turn.jsonl"]
    assert json.loads(json.dumps(result)) == result


def test_codex_first_turn_is_extracted_once_despite_being_recorded_twice() -> None:
    result = envelope_for(FIXTURES / "codex-first-turn.jsonl")
    assert result["status"] == "pass"
    assert result["data"]["format"]["detected"] == "codex"
    assert result["data"]["stats"]["userTurns"] == 2, "event_msg + response_item deduplicated"
    assert result["data"]["anchor"]["statedGoal"].startswith("Ship the onboarding flow")
    assert result["data"]["anchor"]["unmatchedSentences"] == []
    assert result["data"]["anchor"]["additionalGoals"] == [
        "Add a smoke test that runs the installer end to end.",
        "Verify the public catalog boundary stays unchanged.",
    ]
    assert "input.ambiguous-initial-turn" not in _ids(result)
    assert "anchor.unmatched-sentences" not in _ids(result)


def test_later_competing_instructions_do_not_replace_the_first_turn() -> None:
    result = envelope_for(FIXTURES / "long-competing.jsonl")
    assert result["status"] == "warn"  # same first turn as the Claude case: one unmatched sentence
    assert result["data"]["stats"]["userTurns"] == 12
    anchor = result["data"]["anchor"]
    assert anchor["statedGoal"].startswith("Ship the onboarding flow")
    assert "delete the database" not in json.dumps(anchor)
    assert "delete the database" not in result["data"]["markdown"]
    assert "user turns observed: 12" in result["data"]["markdown"]


# --- degradation, reported not repaired -----------------------------------


def test_truncated_jsonl_still_anchors_but_says_so() -> None:
    result = envelope_for(FIXTURES / "truncated.jsonl")
    assert result["status"] == "warn"
    assert result["exitCode"] == 0
    warning = _finding(result, "input.unparseable-lines")
    assert warning["severity"] == "warn"
    assert warning["summary"].startswith("2 of 5 line(s)")
    assert result["data"]["stats"] == {
        "lines": 5,
        "unparseableLines": 2,
        "skippedUserRecords": 0,
        "userTurns": 1,
        "userTurnsBeforeFirstAssistant": 1,
    }
    assert result["data"]["anchor"]["statedGoal"].startswith("Ship the onboarding flow")


def test_missing_first_turn_is_the_products_own_error_not_an_invented_anchor() -> None:
    result = envelope_for(FIXTURES / "missing-first-turn.jsonl")
    assert result["status"] == "fail"
    assert result["exitCode"] == 1
    error = _finding(result, "input.error")
    assert error["summary"] == "no user turns found in session"
    assert result["data"]["anchor"] is None
    assert result["data"]["markdown"] is None
    assert result["data"]["stats"]["skippedUserRecords"] == 2
    assert result["data"]["stats"]["userTurns"] == 0


def test_ambiguous_initial_turns_use_turn_one_and_warn() -> None:
    result = envelope_for(FIXTURES / "ambiguous-initial.jsonl")
    assert result["status"] == "warn"
    assert result["exitCode"] == 0
    warning = _finding(result, "input.ambiguous-initial-turn")
    assert warning["summary"].startswith("2 user turns appear before the first assistant reply")
    assert result["data"]["anchor"]["statedGoal"] == "Draft the release notes for 0.3"
    assert "audit the changelog" not in result["data"]["anchor"]["statedGoal"]
    assert result["data"]["stats"]["userTurnsBeforeFirstAssistant"] == 2


def test_garbage_file_fails_with_every_line_counted() -> None:
    result = envelope_for(FIXTURES / "garbage.jsonl")
    assert result["status"] == "fail"
    assert result["exitCode"] == 1
    assert _finding(result, "input.error")["summary"] == "no user turns found in session"
    assert result["data"]["stats"]["lines"] == 3
    assert result["data"]["stats"]["unparseableLines"] == 3


def test_missing_file_is_the_products_own_error(tmp_path) -> None:
    result = envelope_for(tmp_path / "nope.jsonl")
    assert result["status"] == "fail"
    assert result["exitCode"] == 1
    assert _finding(result, "input.error")["summary"] == "session jsonl not found: nope.jsonl"
    assert result["data"]["readPaths"] == []


def test_full_mode_marks_a_truncated_first_turn(tmp_path) -> None:
    long_turn = "Build the thing. " * 400  # > 4000 chars
    path = tmp_path / "long.jsonl"
    path.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": long_turn}}) + "\n",
        encoding="utf-8",
    )
    result = envelope_for(path, anchor_mode="full")
    assert result["status"] == "warn"
    assert _finding(result, "anchor.full-text-truncated")["severity"] == "warn"
    assert result["data"]["anchor"]["fullTruncated"] is True
    assert "…[truncated]" in result["data"]["markdown"]


# --- privacy and effects ---------------------------------------------------


def test_only_the_explicit_session_path_is_opened(monkeypatch) -> None:
    opened: list[str] = []
    real_open = builtins.open

    def recording_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", recording_open)
    session = FIXTURES / "claude-first-turn.jsonl"
    envelope_for(session)
    assert opened, "the session file must be read"
    assert {Path(p).resolve() for p in opened} == {session.resolve()}


def test_the_emitter_never_discovers_sessions_or_touches_home() -> None:
    source = (REPO_ROOT / "src" / "hermes_blind" / "evidence.py").read_text(encoding="utf-8")
    assert not re.search(r"Path\.home|expanduser|\.claude|\.codex|glob\(", source)


def test_paths_are_reported_by_basename_only(tmp_path) -> None:
    session = tmp_path / "deep" / "private-dir" / "s.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "Ship it."}}) + "\n"
    )
    text = json.dumps(envelope_for(session))
    assert "private-dir" not in text
    assert str(tmp_path) not in text


def test_a_run_writes_nothing_and_needs_nothing_from_home(tmp_path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hermes_blind.evidence",
            "--session",
            str(FIXTURES / "claude-first-turn.jsonl"),
        ],
        cwd=cwd,
        env={
            **os.environ,
            "HOME": str(fake_home),
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "warn"  # one unmatched sentence, reported
    assert list(cwd.iterdir()) == []
    assert list(fake_home.iterdir()) == []


# --- contract details ------------------------------------------------------


def test_input_hash_follows_content_format_mode_and_turn(tmp_path) -> None:
    a = envelope_for(FIXTURES / "claude-first-turn.jsonl")["inputHash"]
    again = envelope_for(FIXTURES / "claude-first-turn.jsonl")["inputHash"]
    other_file = envelope_for(FIXTURES / "long-competing.jsonl")["inputHash"]
    other_mode = envelope_for(FIXTURES / "claude-first-turn.jsonl", anchor_mode="full")["inputHash"]
    other_turn = envelope_for(FIXTURES / "claude-first-turn.jsonl", turn=3)["inputHash"]
    assert a == again
    assert len({a, other_file, other_mode, other_turn}) == 4
    copy = tmp_path / "renamed.jsonl"
    copy.write_bytes((FIXTURES / "claude-first-turn.jsonl").read_bytes())
    assert envelope_for(copy)["inputHash"] == a, "same bytes, same hash, regardless of name"


def test_invalid_options_are_refused_before_reading() -> None:
    with pytest.raises(ValueError, match="unknown format"):
        envelope_for(FIXTURES / "claude-first-turn.jsonl", fmt="yaml")
    with pytest.raises(ValueError, match="unknown anchor mode"):
        envelope_for(FIXTURES / "claude-first-turn.jsonl", anchor_mode="everything")


def test_cli_requires_an_explicit_session(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        evidence.main([])
    assert exit_info.value.code == 2
    capsys.readouterr()
    assert evidence.main(["--session", str(FIXTURES / "codex-first-turn.jsonl")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "pass"
    assert evidence.main(["--session", str(FIXTURES / "garbage.jsonl")]) == 1
    capsys.readouterr()


def test_overall_status_is_the_worst_finding_present() -> None:
    assert evidence.worst_status([]) == "pass"
    assert (
        evidence.worst_status(
            [evidence.finding("a", "warn", "x"), evidence.finding("b", "unknown", "y")]
        )
        == "unknown"
    )
    with pytest.raises(ValueError):
        evidence.finding("a", "bad", "x")


def test_build_anchor_exposes_the_facts_the_markdown_states() -> None:
    anchor = build_anchor(["Ship it. Then verify it. Thanks.", "Continue."], 4, session_name="s.jsonl")
    assert anchor.stated_goal == "Ship it"
    assert anchor.additional_goals == ["Then verify it."]
    assert anchor.sentences_total == 3
    assert anchor.unmatched_sentences == ["Thanks."]
    assert anchor.user_turns == 2
    assert anchor.turn == 4
    assert "applied at turn 4" in anchor.markdown
    assert anchor.markdown.endswith("the goal.\n")


def test_git_sha_marks_a_tree_whose_commit_does_not_describe_the_code(tmp_path) -> None:
    assert evidence.git_sha(tmp_path) is None

    def run(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    run("init", "-q")
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one\n")
    run("add", "-A")
    run("commit", "-qm", "first")
    clean = evidence.git_sha(tmp_path)
    assert clean and len(clean) == 40
    (tmp_path / "a.txt").write_text("two\n")
    assert evidence.git_sha(tmp_path) == f"{clean}-dirty"
