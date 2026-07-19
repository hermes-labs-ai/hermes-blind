"""Tests for the intentionally narrow public CLI."""

from hermes_blind.cli import main


def test_help_lists_apply_only(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "hermes-blind apply" in out
    assert "experiment" not in out


def test_unknown_subcommand_is_usage_error(capsys):
    assert main(["experiment"]) == 2
    assert "unknown subcommand" in capsys.readouterr().err
