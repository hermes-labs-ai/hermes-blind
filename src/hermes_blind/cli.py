"""Command-line interface for the public hermes-blind package.

The public CLI intentionally exposes only the two deterministic operations
implemented by hermes_blind.apply:

* wrap an evaluation prompt with a named scaffold; or
* extract a recovery anchor from a Claude Code or Codex session JSONL.

Research harnesses used to evaluate candidate mechanisms are not part of the
public runtime surface.
"""
from __future__ import annotations

import sys

from hermes_blind.apply import main as apply_main
from hermes_blind.hermes_agent_hook import main as hermes_agent_hook_main


def _print_help() -> None:
    print(
        """hermes-blind — deterministic prompt and session recovery scaffolds

Usage:
  hermes-blind apply [options]
  hermes-blind hermes-agent-hook --at-turn N
  hermes-blind --help

Run a subcommand with --help for all options.
"""
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        _print_help()
        return 0
    if args[0] == "apply":
        return apply_main(args[1:])
    if args[0] == "hermes-agent-hook":
        return hermes_agent_hook_main(args[1:])
    print(f"hermes-blind: unknown subcommand {args[0]!r}", file=sys.stderr)
    print("Run 'hermes-blind --help' for usage.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
