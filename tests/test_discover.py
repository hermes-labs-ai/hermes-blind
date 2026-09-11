"""Tests for `--latest` session discovery (hermes_blind.discover).

Every test builds a fake home directory on disk and sets HOME (or
CLAUDE_CONFIG_DIR / CODEX_HOME) at it, so nothing here reads the real
machine's session logs.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hermes_blind.apply import main as apply_main  # noqa: E402
from hermes_blind.discover import (  # noqa: E402
    DiscoveryError,
    claude_projects_dir,
    codex_sessions_dir,
    discover_latest,
    encoded_project_names,
)
from hermes_blind.evidence import main as evidence_main  # noqa: E402

PROJECT = Path("/home/dev/app")


def _write(path: Path, records: list[dict], mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    os.utime(path, (mtime, mtime))
    return path


def _claude_session(text: str = "Ship the onboarding flow.") -> list[dict]:
    return [
        {"type": "user", "message": {"role": "user", "content": text}},
        {"type": "assistant", "message": {"role": "assistant", "content": "ok"}},
    ]


def _claude_subagent_only() -> list[dict]:
    """A sub-agent log: every user record is a sidechain or a tool result."""
    return [
        {
            "type": "user",
            "isSidechain": True,
            "message": {"role": "user", "content": "Search the repo for X."},
        },
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {"role": "assistant", "content": "found"},
        },
    ]


def _codex_rollout(text: str = "Drain the review queue.") -> list[dict]:
    return [
        {"type": "session_meta", "payload": {"id": "abc"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": text}},
    ]


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An empty fake home directory, with HOME pointed at it."""
    fake = tmp_path / "home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
    return fake


def _project_dir(home: Path, project: Path = PROJECT) -> Path:
    return home / ".claude" / "projects" / encoded_project_names(project)[0]


# ---------------------------------------------------------------------------
# Path convention
# ---------------------------------------------------------------------------


def test_project_directory_name_is_the_path_with_separators_as_dashes():
    assert encoded_project_names(Path("/home/dev/app"))[0] == "-home-dev-app"


def test_a_punctuated_path_also_offers_a_folded_candidate():
    names = encoded_project_names(Path("/home/dev/my.app"))
    assert names[0] == "-home-dev-my.app"
    assert "-home-dev-my-app" in names


def test_roots_default_under_home(home):
    assert claude_projects_dir({}) == home / ".claude" / "projects"
    assert codex_sessions_dir({}) == home / ".codex" / "sessions"


# ---------------------------------------------------------------------------
# Choosing a log
# ---------------------------------------------------------------------------


def test_picks_the_newest_log_in_this_projects_directory(home):
    directory = _project_dir(home)
    _write(directory / "old.jsonl", _claude_session("Old goal."), 1_000)
    newest = _write(directory / "new.jsonl", _claude_session("New goal."), 2_000)

    found = discover_latest(cwd=PROJECT)

    assert found.path == newest
    assert found.fmt == "claude"
    assert found.skipped == 0


def test_a_newer_subagent_only_log_is_skipped(home):
    directory = _project_dir(home)
    real = _write(directory / "real.jsonl", _claude_session(), 1_000)
    _write(directory / "sub.jsonl", _claude_subagent_only(), 9_000)

    found = discover_latest(cwd=PROJECT)

    assert found.path == real
    assert found.skipped == 1


def test_other_projects_are_not_considered_when_cwd_is_given(home):
    _write(
        _project_dir(home) / "mine.jsonl", _claude_session("Mine."), 1_000
    )
    other = home / ".claude" / "projects" / "-home-dev-other"
    _write(other / "theirs.jsonl", _claude_session("Theirs."), 9_000)

    assert discover_latest(cwd=PROJECT).path.name == "mine.jsonl"


def test_falls_back_to_all_projects_only_when_cwd_is_not_given(home, monkeypatch):
    elsewhere = home / ".claude" / "projects" / "-home-dev-elsewhere"
    fallback = _write(elsewhere / "s.jsonl", _claude_session(), 1_000)
    empty = home / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    assert discover_latest().path == fallback
    with pytest.raises(DiscoveryError, match="no session log found"):
        discover_latest(cwd=PROJECT)


def test_codex_rollouts_are_found_under_the_dated_directories(home):
    rollout = _write(
        home / ".codex" / "sessions" / "2026" / "09" / "11" / "rollout-2026-09-11.jsonl",
        _codex_rollout(),
        1_000,
    )

    found = discover_latest(fmt="codex")

    assert found.path == rollout
    assert found.fmt == "codex"


def test_auto_ranks_claude_and_codex_logs_together_by_mtime(home):
    _write(_project_dir(home) / "c.jsonl", _claude_session(), 1_000)
    rollout = _write(
        home / ".codex" / "sessions" / "2026" / "09" / "11" / "rollout-x.jsonl",
        _codex_rollout(),
        5_000,
    )

    assert discover_latest(cwd=PROJECT).path == rollout
    assert discover_latest(fmt="claude", cwd=PROJECT).path.name == "c.jsonl"


# ---------------------------------------------------------------------------
# Environment overrides
# ---------------------------------------------------------------------------


def test_claude_config_dir_overrides_the_home_location(home, monkeypatch, tmp_path):
    config = tmp_path / "elsewhere"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    _write(_project_dir(home) / "ignored.jsonl", _claude_session(), 9_000)
    wanted = _write(
        config / "projects" / encoded_project_names(PROJECT)[0] / "wanted.jsonl",
        _claude_session(),
        1_000,
    )

    assert discover_latest(fmt="claude", cwd=PROJECT).path == wanted


def test_codex_home_overrides_the_home_location(home, monkeypatch, tmp_path):
    codex = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(codex))
    _write(
        home / ".codex" / "sessions" / "2026" / "09" / "11" / "rollout-ignored.jsonl",
        _codex_rollout(),
        9_000,
    )
    wanted = _write(
        codex / "sessions" / "2026" / "09" / "11" / "rollout-wanted.jsonl",
        _codex_rollout(),
        1_000,
    )

    assert discover_latest(fmt="codex").path == wanted


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_nothing_found_names_every_location_it_looked_in(home):
    with pytest.raises(DiscoveryError) as error:
        discover_latest(cwd=PROJECT)
    message = str(error.value)
    assert "no session log found" in message
    assert ".claude/projects/-home-dev-app" in message
    assert ".codex/sessions" in message
    assert "--session" in message


def test_only_subagent_logs_is_a_refusal_not_a_guess(home):
    _write(_project_dir(home) / "sub.jsonl", _claude_subagent_only(), 1_000)

    with pytest.raises(DiscoveryError, match="none contains a user turn"):
        discover_latest(cwd=PROJECT)


def test_two_logs_with_the_same_mtime_are_ambiguous(home):
    directory = _project_dir(home)
    _write(directory / "a.jsonl", _claude_session("A."), 4_000)
    _write(directory / "b.jsonl", _claude_session("B."), 4_000)

    with pytest.raises(DiscoveryError, match="share the newest modification time"):
        discover_latest(cwd=PROJECT)


def test_an_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="unknown format"):
        discover_latest(fmt="vim")


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_apply_latest_writes_the_anchor_and_names_the_log_on_stderr(home, tmp_path, capsys):
    chosen = _write(
        _project_dir(home) / "s.jsonl", _claude_session("Ship the onboarding flow."), 1_000
    )
    out = tmp_path / "recovery.md"

    assert apply_main(["--latest", "--cwd", str(PROJECT), "--turn", "9", "--out", str(out)]) == 0

    captured = capsys.readouterr()
    assert str(chosen) in captured.err
    assert "Ship the onboarding flow" in out.read_text(encoding="utf-8")


def test_apply_latest_and_session_are_mutually_exclusive(home, capsys):
    with pytest.raises(SystemExit) as exit_info:
        apply_main(["--latest", "--session", "x.jsonl"])
    assert exit_info.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_apply_cwd_without_latest_is_an_error(home, capsys):
    assert apply_main(["--cwd", str(PROJECT), "--prompt", "hi"]) == 2
    assert "--cwd only applies with --latest" in capsys.readouterr().err


def test_apply_latest_exits_1_when_nothing_is_found(home, capsys):
    assert apply_main(["--latest", "--cwd", str(PROJECT)]) == 1
    assert "no session log found" in capsys.readouterr().err


def test_apply_session_is_unchanged_by_discovery(tmp_path, capsys):
    session = _write(tmp_path / "explicit.jsonl", _claude_session("Explicit goal."), 1_000)

    assert apply_main(["--session", str(session)]) == 0
    assert "Explicit goal" in capsys.readouterr().out


def test_evidence_latest_emits_an_envelope_for_the_discovered_log(home, capsys):
    chosen = _write(_project_dir(home) / "s.jsonl", _claude_session(), 1_000)

    assert evidence_main(["--latest", "--cwd", str(PROJECT)]) == 0

    captured = capsys.readouterr()
    assert str(chosen) in captured.err
    envelope = json.loads(captured.out)
    assert envelope["data"]["sessionName"] == "s.jsonl"
    assert envelope["data"]["format"]["detected"] == "claude"


def test_evidence_requires_a_session_or_latest(capsys):
    with pytest.raises(SystemExit) as exit_info:
        evidence_main([])
    assert exit_info.value.code == 2
