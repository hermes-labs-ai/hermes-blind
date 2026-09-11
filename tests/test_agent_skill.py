"""Tests for the Claude Code Agent Skill entry surface.

`.claude/skills/hermes-blind/SKILL.md` is a discovery surface, not new
runtime behavior: it documents the exact `hermes-blind apply` invocation a
host agent should run to recover a session's original goal. These tests
verify the file is well-formed and that its documented command actually
does what it says against the real package — a positive path (a real
first-turn fixture) and an adversarial one (a malformed session file).
"""
from __future__ import annotations

from pathlib import Path

from hermes_blind.apply import main

SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "hermes-blind" / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "SKILL.md must start with a YAML frontmatter block"
    end = text.index("\n---", 4)
    block = text[4:end]
    fields = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text[end + 4:]


def test_skill_frontmatter_is_well_formed():
    text = SKILL_PATH.read_text(encoding="utf-8")
    fields, body = _frontmatter(text)
    # name must match the directory name for Claude Code to discover it correctly.
    assert fields["name"] == SKILL_PATH.parent.name == "hermes-blind"
    assert fields["description"], "description is required for skill discovery/triggering"
    assert "hermes-blind apply" in body


def test_skill_never_auto_executes_a_command():
    """Guard against someone adding a `!`-prefixed auto-exec line.

    hermes-blind apply --out writes a file; auto-running it on skill load
    (before a real session path is known) would write to an unintended
    path. The skill must stay instructional, not self-executing.
    """
    text = SKILL_PATH.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("!")]
    assert lines == [], f"SKILL.md must not auto-execute commands, found: {lines}"


def test_documented_command_recovers_a_real_session(tmp_path):
    """Positive check: the exact command line from SKILL.md works end to end."""
    out = tmp_path / "recovery.md"
    rc = main([
        "--session", "fixtures/lab/claude-first-turn.jsonl",
        "--format", "auto",
        "--turn", "9",
        "--out", str(out),
    ])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Recovery scaffold" in text
    assert "Ship the onboarding flow" in text


def test_documented_command_refuses_malformed_session(tmp_path, capsys):
    """Adversarial check: a malformed session file fails safely, no anchor invented."""
    out = tmp_path / "recovery.md"
    rc = main([
        "--session", "fixtures/lab/garbage.jsonl",
        "--format", "auto",
        "--turn", "9",
        "--out", str(out),
    ])
    assert rc != 0
    assert not out.exists(), "no anchor should be written when no user turn is found"
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_latest_instruction_carries_a_fallback_for_an_older_pinned_runner():
    """The skill pins an exact release; a newer flag must degrade, not hard-fail.

    SKILL.md pins `uvx hermes-blind==X` so the agent never fetches an
    unreviewed release. That pin and the flags the skill teaches move on
    different schedules: a flag merged here is not on PyPI until the release
    ships, so between the two an agent following step 2 verbatim gets
    `error: unrecognized arguments: --latest` and exit 2. Step 3 must name
    that case, so the agent falls back to --session instead of stopping.
    """
    text = SKILL_PATH.read_text(encoding="utf-8")
    if "--latest" not in text:
        return
    assert "unrecognized arguments: --latest" in text, (
        "SKILL.md teaches --latest but does not tell the agent what to do when "
        "the pinned runner predates it"
    )
    assert "--session" in text, "the fallback must name the explicit --session path"
