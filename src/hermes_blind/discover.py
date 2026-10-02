"""Find the session log for the session you are in (``apply --latest``).

Step 2 of the recovery flow used to be "find this session's JSONL by hand".
This module does that lookup instead, from the two locations the tools
actually write to:

* Claude Code — ``<config>/projects/<encoded cwd>/<session>.jsonl``, where
  ``<config>`` is ``$CLAUDE_CONFIG_DIR`` if set and ``~/.claude`` otherwise,
  and ``<encoded cwd>`` is the project's absolute path with the separators
  replaced by ``-`` (``/home/u/p`` → ``-home-u-p``).
* Codex — ``<home>/sessions/YYYY/MM/DD/rollout-*.jsonl``, where ``<home>`` is
  ``$CODEX_HOME`` if set and ``~/.codex`` otherwise.

Discovery only ever *chooses* a path: it reads candidate files to ask the
existing parser whether they contain a user turn (a sub-agent-only log has
none and is not the session you are in), and it writes nothing. It happens
only when ``--latest`` is passed; ``--session`` remains explicit.

Nothing is guessed: when no candidate is found, or when the two newest
candidates are indistinguishable, discovery refuses and says what to pass
instead.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from hermes_blind.apply import (
    ParseStats,
    _iter_user_texts,
    _iter_user_texts_codex,
)

FORMATS = ("auto", "claude", "codex")

# How many skipped logs are named in stderr output. The total is always
# reported; the cap only keeps the diagnostic short when many logs pile up.
MAX_SKIPPED_SHOWN = 5


class DiscoveryError(Exception):
    """No session log could be chosen. The message is user-facing."""


@dataclass(frozen=True)
class SkippedLog:
    """A newer candidate log that discovery rejected, and why.

    ``name`` is the file's basename only: session paths are not emitted in
    full by default (see AGENTS.md). ``reason`` is a short, fixed phrase.
    """

    name: str
    reason: str


@dataclass(frozen=True)
class Discovery:
    """The session log discovery picked, and how it got there.

    ``fmt`` is the concrete dialect of the chosen file ("claude" or "codex"),
    so the caller does not have to sniff it again. ``scope`` names the
    location searched and ``skipped`` counts newer candidates that carried no
    user turn — both are reported to the user, not acted on.
    ``skipped_logs`` names the first :data:`MAX_SKIPPED_SHOWN` of them, newest
    first, with the reason each was rejected; ``skipped`` stays the full count.
    """

    path: Path
    fmt: str
    scope: str
    skipped: int
    skipped_logs: tuple[SkippedLog, ...] = ()


def claude_projects_dir(env: dict[str, str] | None = None) -> Path:
    """Where Claude Code keeps per-project session logs."""
    environ = os.environ if env is None else env
    configured = environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return base / "projects"


def codex_sessions_dir(env: dict[str, str] | None = None) -> Path:
    """Where Codex keeps rollout logs."""
    environ = os.environ if env is None else env
    configured = environ.get("CODEX_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return base / "sessions"


def encoded_project_names(cwd: Path) -> list[str]:
    """Candidate Claude Code project-directory names for ``cwd``, best first.

    The documented encoding is the absolute path with separators replaced by
    ``-``. Some client versions also fold other punctuation into ``-``; that
    variant is tried second so a project path containing a dot or a space is
    still found. Both are only ever used to look for a directory.
    """
    primary = str(cwd).replace(os.sep, "-")
    names = [primary]
    folded = re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    if folded != primary:
        names.append(folded)
    return names


def _files(directory: Path, pattern: str) -> list[Path]:
    try:
        return sorted(p for p in directory.glob(pattern) if p.is_file())
    except OSError:
        return []


def _skip_reason(path: Path, fmt: str) -> str | None:
    """Why ``path`` cannot be the current session, or ``None`` if it can.

    A usable log has at least one user turn according to the existing parser.
    A sub-agent-only log and an empty log have none; an unreadable file or one
    that is not valid UTF-8 cannot be read at all. Lines that are not valid
    JSON are skipped by the parser, so they are only mentioned when they are
    the reason no user turn was found.
    """
    iterator = _iter_user_texts_codex if fmt == "codex" else _iter_user_texts
    stats = ParseStats()
    generator = iterator(path, stats)
    try:
        if next(generator, None) is not None:
            return None
    except (OSError, UnicodeDecodeError):
        return "unreadable (cannot be read or is not valid UTF-8)"
    finally:
        generator.close()
    if stats.unparseable_lines:
        return f"no user turn ({stats.unparseable_lines} unparseable line(s))"
    return "no user turn"


def _has_user_turn(path: Path, fmt: str) -> bool:
    """Whether the existing parser finds at least one user turn in ``path``."""
    return _skip_reason(path, fmt) is None


def _claude_pool(
    cwd: Path | None, env: dict[str, str] | None, searched: list[str]
) -> list[tuple[str, str, list[Path]]]:
    projects = claude_projects_dir(env)
    target = (Path(cwd) if cwd is not None else Path.cwd()).expanduser()
    # Claude Code encodes the path it was *launched with*, which is not always
    # the fully resolved one: a symlinked project directory (and on macOS
    # /tmp -> /private/tmp or /home -> /System/Volumes/Data/home) records the
    # literal path. Resolving first and encoding only that misses those logs
    # entirely, so try the literal encoding first and the resolved one after.
    candidates = [target]
    try:
        resolved = target.resolve()
    except OSError:  # pragma: no cover - resolve() is effectively total on POSIX
        resolved = target
    if resolved != target:
        candidates.append(resolved)
    names: list[str] = []
    for candidate in candidates:
        for name in encoded_project_names(candidate):
            if name not in names:
                names.append(name)
    files: list[Path] = []
    matched: str | None = None
    for name in names:
        found = _files(projects / name, "*.jsonl")
        if found and matched is None:
            matched = name
        files.extend(found)
    searched.append(f"{projects / names[0]}/*.jsonl")
    if files:
        return [("claude", f"{projects / (matched or names[0])}", files)]
    if cwd is not None:
        # An explicit --cwd is a request for that project, not for whatever
        # else is on disk. Do not widen it.
        return []
    every = _files(projects, "*/*.jsonl")
    searched.append(f"{projects}/*/*.jsonl (no log for {target})")
    if every:
        return [("claude", f"{projects} (all projects; none for {target})", every)]
    return []


def _codex_pool(
    env: dict[str, str] | None, searched: list[str]
) -> list[tuple[str, str, list[Path]]]:
    sessions = codex_sessions_dir(env)
    searched.append(f"{sessions}/**/rollout-*.jsonl")
    files = _files(sessions, "**/rollout-*.jsonl")
    return [("codex", str(sessions), files)] if files else []


def discover_latest(
    fmt: str = "auto",
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> Discovery:
    """Choose the most recently modified session log that carries a user turn.

    ``fmt`` limits the search to one tool's logs; "auto" considers both and
    the newest file wins. ``cwd`` scopes the Claude Code search to one
    project directory — when it is omitted the current working directory is
    used, and a search that finds nothing for it widens to every project
    directory. An explicit ``cwd`` never widens. Codex rollouts are not
    per-project and are always searched whole.

    Raises :class:`DiscoveryError` when nothing is found, when no candidate
    carries a user turn, or when the two newest candidates share a
    modification time and so cannot be ranked.
    """
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; choose auto, claude, or codex")
    searched: list[str] = []
    pools: list[tuple[str, str, list[Path]]] = []
    if fmt in ("auto", "claude"):
        pools.extend(_claude_pool(cwd, env, searched))
    if fmt in ("auto", "codex"):
        pools.extend(_codex_pool(env, searched))

    entries: list[tuple[int, Path, str, str]] = []
    for pool_fmt, scope, files in pools:
        for path in files:
            try:
                mtime = path.stat().st_mtime_ns
            except OSError:
                continue
            entries.append((mtime, path, pool_fmt, scope))
    if not entries:
        looked = "\n".join(f"  {location}" for location in searched)
        raise DiscoveryError(
            "no session log found. Looked in:\n"
            f"{looked}\n"
            "Pass --session <path> to name one explicitly."
        )
    # Newest first; the path breaks mtime ties deterministically so the
    # ambiguity check below sees the same pair on every run.
    entries.sort(key=lambda entry: (-entry[0], str(entry[1])))

    skipped = 0
    skipped_logs: list[SkippedLog] = []
    chosen: tuple[int, Path, str, str] | None = None
    runner_up: tuple[int, Path, str, str] | None = None
    for entry in entries:
        reason = _skip_reason(entry[1], entry[2])
        if reason is not None:
            if chosen is None:
                skipped += 1
                if len(skipped_logs) < MAX_SKIPPED_SHOWN:
                    skipped_logs.append(SkippedLog(entry[1].name, reason))
            continue
        if chosen is None:
            chosen = entry
            continue
        runner_up = entry
        break

    if chosen is None:
        raise DiscoveryError(
            f"found {len(entries)} session log(s) but none contains a user turn "
            "(sub-agent-only logs carry none).\n"
            f"{_skipped_lines(skipped_logs, skipped)}"
            "Pass --session <path> to name one explicitly."
        )
    if runner_up is not None and runner_up[0] == chosen[0]:
        raise DiscoveryError(
            "two session logs share the newest modification time, so the "
            "current one cannot be identified:\n"
            f"  {chosen[1]}\n"
            f"  {runner_up[1]}\n"
            "Pass --session <path> to name one explicitly."
        )
    return Discovery(
        path=chosen[1],
        fmt=chosen[2],
        scope=chosen[3],
        skipped=skipped,
        skipped_logs=tuple(skipped_logs),
    )


def _skipped_lines(logs: list[SkippedLog] | tuple[SkippedLog, ...], total: int) -> str:
    """Indented ``name: reason`` lines for skipped logs, each ending in a newline.

    Names at most :data:`MAX_SKIPPED_SHOWN` logs and says how many were left out.
    """
    lines = [f"  skipped {log.name}: {log.reason}\n" for log in logs]
    hidden = total - len(logs)
    if hidden > 0:
        lines.append(f"  ... and {hidden} more\n")
    return "".join(lines)


def describe(found: Discovery) -> str:
    """The chosen log, for stderr; skipped newer logs follow on indented lines."""
    line = f"using {found.fmt} session log: {found.path}"
    if found.skipped:
        line += f" ({found.skipped} newer log(s) skipped)"
        line += "\n" + _skipped_lines(found.skipped_logs, found.skipped).rstrip("\n")
    return line
