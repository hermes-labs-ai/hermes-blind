"""
hermes_blind/evidence.py

Emits a recovery-anchor extraction as a Hermes Reliability Lab result
envelope (`hermes.reliability-lab.result/1`): tool, version, status, input
hash, lossless findings, exit code, timestamp, optional Git SHA — with the
ordinary markdown scaffold embedded verbatim and the facts it was rendered
from alongside it.

Extraction semantics are untouched: this calls the same parser and the same
anchor builder `hermes-blind apply --session` uses. What it adds is
observability — how many lines parsed, whether the first turn was
unambiguous — and it reports rather than repairs: an unparseable line, an
ambiguous first turn, or a truncated full-text anchor becomes a finding, and
a file with no user turn is the product's own error, exit 1.

The session is named by `--session`, or found by `--latest` — the same
lookup `apply --latest` performs, which reads candidate logs to rank them and
prints the one it chose to stderr. Nothing is written, nothing leaves the
machine, and the path is reported in the envelope by basename only.

    python -m hermes_blind.evidence --session fixtures/lab/claude-first-turn.jsonl
    python -m hermes_blind.evidence --latest
    python -m hermes_blind.evidence --session rollout.jsonl --format codex --anchor-mode full

Added in v0.2.0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_blind import __version__
from hermes_blind.apply import (
    AnchorResult,
    ParseStats,
    _iter_user_texts,
    _iter_user_texts_codex,
    _sniff_format,
    build_anchor,
)

ENVELOPE = "hermes.reliability-lab.result/1"
TOOL = "hermes-blind"

#: Ordered worst-last; the run's status is the worst finding it carries.
STATUS_ORDER = ("pass", "warn", "unknown", "fail")


# ---------------------------------------------------------------------------
# Envelope primitives (mirrors the other product-owned emitters; not a shared SDK)
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_hash(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def finding(
    identifier: str,
    severity: str,
    summary: str,
    detail: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    if severity not in STATUS_ORDER:
        raise ValueError(f"unknown severity: {severity}")
    result: dict[str, Any] = {"id": identifier, "severity": severity, "summary": summary}
    if detail is not None:
        result["detail"] = detail
    if path is not None:
        result["path"] = path
    return result


def worst_status(findings: list[dict[str, Any]]) -> str:
    status = "pass"
    for item in findings:
        if STATUS_ORDER.index(item["severity"]) > STATUS_ORDER.index(status):
            status = item["severity"]
    return status


def _git(start: Path, *arguments: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(start), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def git_sha(start: Path) -> str | None:
    """Best-effort commit of the checkout the tool runs from, "-dirty" if unclean, else None."""
    head = _git(start, "rev-parse", "HEAD")
    if head is None or head.returncode or not head.stdout.strip():
        return None
    sha = head.stdout.strip()
    status = _git(start, "status", "--porcelain")
    if status is None or status.returncode:
        return sha
    return f"{sha}-dirty" if status.stdout.strip() else sha


def _timestamp(now: datetime | None = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Extraction with observability
# ---------------------------------------------------------------------------


def _findings_for_stats(stats: ParseStats) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if stats.unparseable_lines:
        findings.append(
            finding(
                "input.unparseable-lines",
                "warn",
                f"{stats.unparseable_lines} of {stats.lines} line(s) were not valid JSON and were skipped.",
                "The parser skips lines it cannot decode and continues. Extraction below used only "
                "what parsed; a truncated or corrupted file can still yield an anchor, and this "
                "finding is how you know that happened.",
            )
        )
    if stats.skipped_user_records:
        findings.append(
            finding(
                "input.skipped-user-records",
                "pass",
                f"{stats.skipped_user_records} user record(s) carried no user-authored text and were skipped.",
                "Tool results, sub-agent (sidechain) records, meta records such as slash-command "
                "output and skill expansions, compaction summaries, interruption markers, and "
                "injected context (system reminders, task notifications, Codex environment "
                "context and AGENTS.md instructions) are not user turns.",
            )
        )
    if stats.user_turns_before_first_assistant >= 2:
        findings.append(
            finding(
                "input.ambiguous-initial-turn",
                "warn",
                f"{stats.user_turns_before_first_assistant} user turns appear before the first assistant reply; turn 1 was used.",
                "The first text-bearing user turn is the anchor by definition. The later ones are "
                "counted as turns, not merged in and not preferred. Decide for yourself whether turn 1 "
                "is the mission.",
            )
        )
    return findings


def _findings_for_anchor(anchor: AnchorResult) -> list[dict[str, Any]]:
    findings = [
        finding(
            "anchor.stated-goal",
            "pass",
            f'stated_goal: "{anchor.stated_goal}"',
            f"first turn: {anchor.first_turn_chars} characters; user turns observed: {anchor.user_turns}",
            f"session:{anchor.session_name}#turn-1",
        )
    ]
    if anchor.anchor_mode == "goals":
        if anchor.additional_goals:
            findings.append(
                finding(
                    "anchor.goal-set",
                    "pass",
                    f"{len(anchor.additional_goals)} additional of {anchor.goal_sentences_total} goal sentences kept "
                    f"({anchor.sentences_total} sentence(s) in turn 1).",
                    "\n".join(f"{i}. {g}" for i, g in enumerate(anchor.additional_goals, 1)),
                )
            )
        else:
            findings.append(
                finding(
                    "anchor.goal-set",
                    "pass",
                    f"No additional goal sentences beyond stated_goal ({anchor.goal_sentences_total} goal sentence(s) "
                    f"of {anchor.sentences_total} in turn 1).",
                )
            )
        if anchor.unmatched_sentences:
            findings.append(
                finding(
                    "anchor.unmatched-sentences",
                    "warn",
                    f"{len(anchor.unmatched_sentences)} of {anchor.sentences_total} sentence(s) in turn 1 carry no goal verb and are not in the goal set.",
                    "The goal-verb list is finite. These sentences were in the first turn and were not kept; "
                    "decide for yourself whether any of them is a goal:\n"
                    + "\n".join(f"- {s}" for s in anchor.unmatched_sentences),
                )
            )
    if anchor.full_truncated:
        findings.append(
            finding(
                "anchor.full-text-truncated",
                "warn",
                f"Turn 1 is {anchor.first_turn_chars} characters; the full-text anchor keeps 4000 and marks the cut.",
            )
        )
    return findings


def _envelope(
    findings: list[dict[str, Any]], inputs: Any, exit_code: int, data: Any
) -> dict[str, Any]:
    return {
        "envelope": ENVELOPE,
        "tool": TOOL,
        "toolVersion": __version__,
        "command": "apply",
        # The same deterministic extraction `apply --session` performs, with no --out.
        "mode": "executed",
        "status": worst_status(findings),
        "inputHash": input_hash(inputs),
        "findings": findings,
        "exitCode": exit_code,
        "timestamp": _timestamp(),
        "gitSha": git_sha(Path(__file__).resolve().parent),
        "data": data,
    }


def envelope_for(
    session: Path,
    *,
    fmt: str = "auto",
    anchor_mode: str = "goals",
    turn: int = 9,
) -> dict[str, Any]:
    """Extract the anchor from an explicit session path and return the run as an envelope.

    Reads exactly one file: ``session``. Writes nothing. Reports the path by
    basename only.
    """
    if fmt not in ("auto", "claude", "codex"):
        raise ValueError(f"unknown format {fmt!r}; choose auto, claude, or codex")
    if anchor_mode not in ("first-sentence", "goals", "full"):
        raise ValueError(f"unknown anchor mode {anchor_mode!r}")

    name = session.name
    inputs: dict[str, Any] = {
        "command": "apply",
        "format": fmt,
        "anchorMode": anchor_mode,
        "turn": turn,
        "sessionSha256": None,
    }
    effects = {"writes": "none", "network": "none"}

    if not session.is_file():
        findings = [
            finding(
                "input.error",
                "fail",
                f"session jsonl not found: {name}",
                "The product's own error, verbatim shape: hermes-blind apply exits 1 with this message.",
                f"session:{name}",
            )
        ]
        return _envelope(
            findings,
            inputs,
            1,
            {
                "sessionName": name,
                "format": {"requested": fmt, "detected": None},
                "anchorMode": anchor_mode,
                "turn": turn,
                "stats": None,
                "anchor": None,
                "markdown": None,
                "effects": effects,
                "readPaths": [],
            },
        )

    inputs["sessionSha256"] = hashlib.sha256(session.read_bytes()).hexdigest()
    detected = _sniff_format(session) if fmt == "auto" else fmt
    stats = ParseStats()
    iterator = _iter_user_texts_codex if detected == "codex" else _iter_user_texts
    user_texts = [text for _, text in iterator(session, stats)]

    findings: list[dict[str, Any]] = [
        finding(
            "input.format",
            "pass",
            f"format: {detected} ({'sniffed' if fmt == 'auto' else 'explicit'})",
            f"{stats.lines} line(s) read; {stats.user_turns} user turn(s) found.",
            f"session:{name}",
        )
    ]
    findings.extend(_findings_for_stats(stats))

    stats_data = {
        "lines": stats.lines,
        "unparseableLines": stats.unparseable_lines,
        "skippedUserRecords": stats.skipped_user_records,
        "userTurns": stats.user_turns,
        "userTurnsBeforeFirstAssistant": stats.user_turns_before_first_assistant,
    }

    try:
        anchor = build_anchor(
            user_texts,
            turn,
            anchor_mode=anchor_mode,
            session_name=name,
            session_label="session file",
        )
    except ValueError as error:
        findings.append(
            finding(
                "input.error",
                "fail",
                f"{error}",
                "The product's own error: hermes-blind apply exits 1 with this message. "
                "There is no first turn to anchor on, so nothing is invented.",
                f"session:{name}",
            )
        )
        return _envelope(
            findings,
            inputs,
            1,
            {
                "sessionName": name,
                "format": {"requested": fmt, "detected": detected},
                "anchorMode": anchor_mode,
                "turn": turn,
                "stats": stats_data,
                "anchor": None,
                "markdown": None,
                "effects": effects,
                "readPaths": [name],
            },
        )

    findings.extend(_findings_for_anchor(anchor))
    return _envelope(
        findings,
        inputs,
        0,
        {
            "sessionName": name,
            "format": {"requested": fmt, "detected": detected},
            "anchorMode": anchor_mode,
            "turn": turn,
            "stats": stats_data,
            "anchor": {
                "statedGoal": anchor.stated_goal,
                "additionalGoals": anchor.additional_goals,
                "goalSentencesTotal": anchor.goal_sentences_total,
                "sentencesTotal": anchor.sentences_total,
                "unmatchedSentences": anchor.unmatched_sentences,
                "firstTurnChars": anchor.first_turn_chars,
                "fullTruncated": anchor.full_truncated,
                "userTurns": anchor.user_turns,
            },
            "markdown": anchor.markdown,
            "effects": effects,
            "readPaths": [name],
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_blind.evidence",
        description=(
            "Extract a recovery anchor from a session JSONL and print the result as a "
            "Reliability Lab envelope. Nothing is written."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", help="Explicit path to a session JSONL.")
    source.add_argument(
        "--latest",
        action="store_true",
        help="Find this session's log automatically, as `apply --latest` does. "
             "Mutually exclusive with --session.",
    )
    parser.add_argument(
        "--cwd",
        help="Project directory whose Claude Code log --latest should look for. "
             "Default: the current directory.",
    )
    parser.add_argument("--format", default="auto", dest="fmt", choices=("auto", "claude", "codex"))
    parser.add_argument(
        "--anchor-mode", default="goals", choices=("first-sentence", "goals", "full")
    )
    parser.add_argument("--turn", type=int, default=9, help="Label only, as in `apply`.")
    args = parser.parse_args(argv)

    if args.cwd and not args.latest:
        print("hermes-blind evidence: --cwd only applies with --latest", file=sys.stderr)
        return 2

    fmt = args.fmt
    if args.latest:
        from hermes_blind.discover import DiscoveryError, describe, discover_latest

        try:
            found = discover_latest(
                fmt=args.fmt,
                cwd=Path(args.cwd).expanduser() if args.cwd else None,
            )
        except DiscoveryError as error:
            print(f"hermes-blind evidence: {error}", file=sys.stderr)
            return 1
        print(f"hermes-blind evidence: {describe(found)}", file=sys.stderr)
        session, fmt = found.path, found.fmt
    else:
        session = Path(args.session)

    result = envelope_for(session, fmt=fmt, anchor_mode=args.anchor_mode, turn=args.turn)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
