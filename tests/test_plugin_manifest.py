"""Tests for the root Claude plugin package (Agent Plugins Marketplace surface).

`.claude-plugin/plugin.json` + `skills/hermes-blind/SKILL.md` at the repo
root make this repo installable as a Claude plugin, alongside the existing
`.claude/skills/hermes-blind/SKILL.md` project-discovery surface used when
this repo is cloned directly. The two SKILL.md copies must never diverge —
that would mean the plugin and the cloned-repo experience document
different behavior — and the manifest's identity fields must track
pyproject.toml rather than being hand-maintained separately.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PROJECT_SKILL = ROOT / ".claude" / "skills" / "hermes-blind" / "SKILL.md"
PLUGIN_SKILL = ROOT / "skills" / "hermes-blind" / "SKILL.md"
PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject_field(name: str) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(name)}\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert match, f"{name} not found in pyproject.toml"
    return match.group(1)


def _pyproject_url(key: str) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(rf'^"{re.escape(key)}"\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert match, f"[project.urls] {key} not found in pyproject.toml"
    return match.group(1)


def test_plugin_skill_is_byte_identical_to_project_skill():
    """The plugin surface and the cloned-repo surface must never diverge."""
    project_bytes = PROJECT_SKILL.read_bytes()
    plugin_bytes = PLUGIN_SKILL.read_bytes()
    assert project_bytes == plugin_bytes, (
        f"{PLUGIN_SKILL} has drifted from {PROJECT_SKILL} — "
        "keep the two copies byte-identical, don't fork the content."
    )


def test_plugin_manifest_identity_matches_pyproject():
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

    assert manifest["name"] == _pyproject_field("name")
    assert manifest["version"] == _pyproject_field("version")
    assert manifest["license"] == _pyproject_field("license")
    assert manifest["repository"] == _pyproject_url("Source")
    assert manifest["homepage"] == _pyproject_url("Homepage")


def test_plugin_manifest_points_at_the_plugin_skill_directory():
    assert PLUGIN_SKILL.exists(), "plugin.json's skills/ directory must contain hermes-blind/SKILL.md"
    fields = PLUGIN_SKILL.read_text(encoding="utf-8")
    assert fields.startswith("---\n"), "plugin SKILL.md must start with a YAML frontmatter block"


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_plugin_validates_strict():
    result = subprocess.run(
        ["claude", "plugin", "validate", str(ROOT), "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"claude plugin validate --strict failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


_UVX_SPEC = re.compile(r"\b(?:uvx|uv tool run)\s+([^\s`]+)")
_PIPX_SPEC = re.compile(r"\bpipx install\s+([^\s`]+)")


def _specs(pattern: re.Pattern[str]) -> list[str]:
    """Every package spec both SKILL.md copies hand to a fetching runner."""
    specs = []
    for skill in (PROJECT_SKILL, PLUGIN_SKILL):
        found = pattern.findall(skill.read_text(encoding="utf-8"))
        assert found, f"{skill} no longer documents a {pattern.pattern} runner"
        specs.extend(found)
    return specs


def _uvx_specs() -> list[str]:
    return _specs(_UVX_SPEC)


def test_skill_uvx_runner_pins_the_released_version():
    """An unpinned `uvx`/`pipx install hermes-blind` would fetch the newest release."""
    from packaging.requirements import Requirement

    version = _pyproject_field("version")
    for spec in _uvx_specs() + _specs(_PIPX_SPEC):
        req = Requirement(spec)
        assert req.name == "hermes-blind", spec
        assert str(req.specifier) == f"=={version}", (
            f"runner spec {spec!r} must pin exactly hermes-blind=={version}"
        )
        assert not (req.url or req.extras or req.marker), spec


@pytest.mark.skipif(
    os.environ.get("HERMES_BLIND_LIVE_UVX") != "1" or shutil.which("uvx") is None,
    reason="live PyPI check; set HERMES_BLIND_LIVE_UVX=1 with uvx installed",
)
def test_skill_uvx_runner_executes_the_pinned_release(tmp_path):
    """Run the documented step-3 command through the pinned uvx runner.

    Opt-in because it resolves the pinned release from the package index.
    """
    (spec,) = set(_uvx_specs())
    out = tmp_path / "recovery.md"
    run = subprocess.run(
        ["uvx", spec, "apply",
         "--session", str(ROOT / "fixtures" / "lab" / "claude-first-turn.jsonl"),
         "--format", "auto", "--turn", "9", "--out", str(out)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "Ship the onboarding flow" in out.read_text(encoding="utf-8")

    installed = subprocess.run(
        ["uvx", "--from", spec, "python", "-c",
         "import importlib.metadata as m; print(m.version('hermes-blind'))"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert installed.stdout.strip() == _pyproject_field("version")
