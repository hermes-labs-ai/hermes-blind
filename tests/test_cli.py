"""Tests for the intentionally narrow public CLI."""

import io
import json

from hermes_blind.cli import main


def test_help_lists_public_operations(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "hermes-blind apply" in out
    assert "hermes-blind hermes-agent-hook" in out
    assert "experiment" not in out


def test_unknown_subcommand_is_usage_error(capsys):
    assert main(["experiment"]) == 2
    assert "unknown subcommand" in capsys.readouterr().err


def _hook_payload(turns):
    return {
        "hook_event_name": "pre_llm_call",
        "session_id": "private-session-id",
        "extra": {
            "user_message": turns[-1],
            "conversation_history": [
                item
                for text in turns
                for item in (
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": "ok"},
                )
            ],
        },
    }


def test_hermes_agent_hook_injects_once_at_user_chosen_turn(monkeypatch, capsys):
    payload = _hook_payload(["Build and verify the release.", "Continue."])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert main(["hermes-agent-hook", "--at-turn", "2"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "Build and verify the release" in result["context"]
    assert "private-session-id" not in result["context"]


def test_hermes_agent_hook_is_noop_on_other_turn(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_hook_payload(["Goal."]))))
    assert main(["hermes-agent-hook", "--at-turn", "9"]) == 0
    assert json.loads(capsys.readouterr().out) == {}


def test_hermes_agent_hook_fails_open_on_malformed_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not-json"))
    assert main(["hermes-agent-hook", "--at-turn", "9"]) == 0
    assert json.loads(capsys.readouterr().out) == {}
