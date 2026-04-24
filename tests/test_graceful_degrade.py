"""Graceful-degradation tests — continuity gate for hermes-seal.

hermes-blind has **no external dependencies** beyond the Python standard
library. It makes no network calls, no subprocess invocations, no file
I/O at runtime, and does not talk to any LLM backend, database, or
external service.

There is therefore nothing to "degrade gracefully" from — the tool has no
failure modes that depend on external state. The tests below document this
explicitly and assert the invariant, so that a future commit that introduces
a dependency will fail this test file and force a reconsideration of
graceful-degradation behavior.
"""

from __future__ import annotations

import importlib.metadata
import sys


def test_no_runtime_dependencies():
    """Invariant: hermes-blind has zero runtime dependencies.

    If this test fails, someone added a dependency to pyproject.toml's
    [project.dependencies] list. That is a change to the tool's shape
    and requires:

    1. A graceful-degradation test in this file exercising the new
       dependency's failure mode (mock it failing, assert exit code +
       human error + no stacktrace leakage).
    2. An SBOM update in sbom.cdx.json.
    3. A CHANGELOG entry noting the new dependency.
    """
    dist = importlib.metadata.distribution("hermes-blind")
    requires = dist.requires or []
    # Filter out optional-dependencies (marked with `extra ==`)
    runtime_deps = [r for r in requires if "extra" not in r.lower()]
    assert runtime_deps == [], (
        f"hermes-blind should have zero runtime deps, found: {runtime_deps}. "
        "See this file's docstring for the required update procedure."
    )


def test_stdlib_only_imports():
    """Invariant: the hermes_blind package imports only stdlib modules.

    Protects against an import silently introducing a dependency that
    pyproject.toml doesn't capture.
    """
    import hermes_blind
    import hermes_blind.scaffold

    modules_touched = {m.split(".")[0] for m in sys.modules if m.startswith("hermes_blind")}
    # hermes_blind and hermes_blind.scaffold — that's the whole package
    expected = {"hermes_blind"}
    assert expected.issubset(modules_touched)

    # Inspect what scaffold.py actually imports
    src = (
        open(hermes_blind.scaffold.__file__).read()  # noqa: SIM115 — tiny file
        if hermes_blind.scaffold.__file__
        else ""
    )
    # Only stdlib imports allowed; re is the only one
    assert "import re" in src
    assert "from __future__" in src
    # No third-party import sneaking in
    for forbidden in ["import anthropic", "import openai", "import requests", "import httpx"]:
        assert forbidden not in src, f"unexpected dependency import: {forbidden}"


def test_extract_disclosure_handles_malformed_input():
    """Continuity: extract_disclosure must not crash on any string input.

    Models produce wildly varying output. extract_disclosure is called in
    downstream logging paths; a crash here could take down the caller's
    pipeline. Verify the function returns None rather than raising on a
    range of odd inputs.
    """
    from hermes_blind import extract_disclosure

    weird_inputs = [
        "",
        "\x00\x01\x02",
        "a" * 100_000,
        "Prior exposure:",  # empty disclosure
        "Prior exposure:\n\n\nScore 5",  # multi-line disclosure
        "prior exposure" * 50,  # pattern repeated
        "\n\n\n",  # whitespace only
        "💀 prior exposure: emoji in disclosure",
    ]
    for weird in weird_inputs:
        # Must not raise
        result = extract_disclosure(weird)
        assert result is None or isinstance(result, str)


def test_wrap_handles_empty_and_unicode_prompts():
    """Continuity: wrap() must not crash on edge-case caller prompts."""
    from hermes_blind import wrap

    # Empty prompt
    assert wrap("") != ""  # scaffold is still prepended

    # Unicode prompt
    assert "你好" in wrap("你好")

    # Very long prompt
    long_prompt = "x" * 50_000
    wrapped = wrap(long_prompt)
    assert wrapped.endswith(long_prompt)
    assert len(wrapped) > len(long_prompt)
