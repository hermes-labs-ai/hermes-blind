"""Hermes Agent shell-hook adapter for one-shot recovery-anchor injection.

The adapter consumes Hermes Agent's documented shell-hook JSON payload on
stdin and emits ``{"context": ...}`` only at a turn explicitly selected by
the user. It does not infer drift or choose an intervention turn.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from hermes_blind.apply import build_recovery_scaffold_from_user_texts


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict)
        and isinstance(part.get("text"), str)
        and part.get("type") in {"text", "input_text"}
    )


def recovery_context_from_payload(
    payload: Any,
    *,
    at_turn: int,
    anchor_mode: str = "goals",
) -> str | None:
    """Return one recovery context block, or ``None`` to fail open."""
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "pre_llm_call":
        return None
    extra = payload.get("extra")
    if not isinstance(extra, dict):
        return None
    history = extra.get("conversation_history")
    if not isinstance(history, list):
        return None

    user_texts = []
    for message in history:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _content_text(message.get("content")).strip()
        if text:
            user_texts.append(text)

    # Current Hermes Agent includes the incoming user message in
    # conversation_history. Keep a compatibility fallback for hosts that
    # expose the same hook contract but provide prior history only.
    current = extra.get("user_message")
    if isinstance(current, str) and current.strip():
        current = current.strip()
        if not user_texts or user_texts[-1] != current:
            user_texts.append(current)

    if len(user_texts) != at_turn:
        return None
    try:
        return build_recovery_scaffold_from_user_texts(
            user_texts,
            at_turn,
            anchor_mode=anchor_mode,
            session_name="Hermes Agent conversation",
        )
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hermes-blind hermes-agent-hook",
        description="Inject a Blind recovery anchor through Hermes Agent's pre_llm_call hook.",
    )
    parser.add_argument(
        "--at-turn",
        type=int,
        required=True,
        help="User-chosen turn at which to inject once; this is not an automatic drift threshold.",
    )
    parser.add_argument(
        "--anchor-mode",
        choices=("first-sentence", "goals", "full"),
        default="goals",
    )
    args = parser.parse_args(argv)
    if args.at_turn < 1:
        parser.error("--at-turn must be at least 1")

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = None
    context = recovery_context_from_payload(
        payload,
        at_turn=args.at_turn,
        anchor_mode=args.anchor_mode,
    )
    json.dump({"context": context} if context else {}, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
