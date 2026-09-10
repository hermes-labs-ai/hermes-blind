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
