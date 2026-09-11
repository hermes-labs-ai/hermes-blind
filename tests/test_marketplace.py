"""Tests for the repository-hosted Claude Code marketplace surface.

`.claude-plugin/marketplace.json` makes this repo installable with
`claude plugin marketplace add hermes-labs-ai/hermes-blind` +
`claude plugin install hermes-blind@hermes-blind`, on top of the existing
`.claude-plugin/plugin.json` root plugin package (test_plugin_manifest.py)
used for local `--plugin-dir .` loading. The marketplace entry must resolve
to that same plugin — no second copy, no hand-maintained version that can
drift from pyproject.toml/plugin.json.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
PLUGIN_SKILL = ROOT / "skills" / "hermes-blind" / "SKILL.md"


def _marketplace() -> dict:
    return json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))


def _plugin() -> dict:
    return json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))


def _hermes_blind_entry(marketplace: dict) -> dict:
    entries = [p for p in marketplace["plugins"] if p["name"] == "hermes-blind"]
    assert len(entries) == 1, "marketplace.json must list hermes-blind exactly once"
    return entries[0]


def test_marketplace_manifest_is_valid_json_with_one_plugin():
    marketplace = _marketplace()
    assert marketplace["name"]
    assert marketplace["owner"]["name"] == "Hermes Labs"
    assert len(marketplace["plugins"]) == 1


def test_marketplace_entry_source_resolves_to_the_root_plugin_manifest():
    """The marketplace source must point at the existing root plugin package.

    Packaging only: this must not fork a second plugin.json into a
    subdirectory. `source` is the repo root itself, where
    `.claude-plugin/plugin.json` already lives.
    """
    entry = _hermes_blind_entry(_marketplace())
    source = entry["source"]
    resolved = (ROOT / source).resolve()
    assert resolved == ROOT.resolve(), (
        f"marketplace source {source!r} must resolve to the repo root, "
        "where the existing .claude-plugin/plugin.json already lives"
    )
    assert PLUGIN_MANIFEST.exists()


def test_marketplace_entry_identity_is_not_hand_duplicated():
    """No second, driftable copy of version/name in the marketplace entry.

    The marketplace entry may repeat `name` and `description` (they must
    match the plugin manifest — checked below) but must not carry its own
    `version`: that field belongs to plugin.json alone, which
    test_plugin_manifest.py already ties to pyproject.toml.
    """
    entry = _hermes_blind_entry(_marketplace())
    plugin = _plugin()
    assert "version" not in entry, (
        "marketplace entry must not hand-maintain a version; "
        "it is sourced from .claude-plugin/plugin.json (and that from pyproject.toml)"
    )
    assert entry["name"] == plugin["name"]
    assert entry["description"] == plugin["description"]
    assert entry["homepage"] == plugin["homepage"]


def test_marketplace_entry_does_not_reference_paths_outside_the_plugin_root():
    """Every path the entry names must stay inside the resolved plugin root.

    A relative path that climbs out of the plugin directory (e.g. `../`)
    would break once Claude Code copies the plugin into its own cache
    directory, away from this repository checkout.
    """
    entry = _hermes_blind_entry(_marketplace())
    assert not entry["source"].startswith(".."), entry["source"]
    plugin_root = (ROOT / entry["source"]).resolve()
    assert str(plugin_root).startswith(str(ROOT.resolve()))


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_marketplace_manifest_validates_strict():
    result = subprocess.run(
        ["claude", "plugin", "validate", str(MARKETPLACE_MANIFEST), "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"claude plugin validate --strict failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_marketplace_install_caches_a_self_contained_skill(tmp_path):
    """Add this repo as a local marketplace, install it, and read the cache.

    Exercises the real `claude plugin marketplace add` / `install` path into
    an isolated `CLAUDE_CONFIG_DIR` (never the machine's real plugin state)
    and asserts the cached copy is self-contained: `skills/hermes-blind/
    SKILL.md` is reachable purely from within the cached plugin directory,
    with no repo-relative path back to this checkout, and its content is
    byte-identical to the source.
    """
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    env = {"CLAUDE_CONFIG_DIR": str(config_dir), "HOME": str(tmp_path), "PATH": _path_env()}

    add = subprocess.run(
        ["claude", "plugin", "marketplace", "add", str(ROOT)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert add.returncode == 0, f"marketplace add failed:\n{add.stdout}\n{add.stderr}"

    install = subprocess.run(
        ["claude", "plugin", "install", "hermes-blind@hermes-blind"],
        capture_output=True, text=True, check=False, env=env,
    )
    assert install.returncode == 0, f"plugin install failed:\n{install.stdout}\n{install.stderr}"

    version = _plugin()["version"]
    cached_root = config_dir / "plugins" / "cache" / "hermes-blind" / "hermes-blind" / version
    cached_skill = cached_root / "skills" / "hermes-blind" / "SKILL.md"
    if cached_root.exists():
        tree = sorted(p.relative_to(cached_root) for p in cached_root.rglob("*"))
    else:
        tree = "cache root missing"
    assert cached_skill.exists(), f"expected cached skill at {cached_skill}; cache tree: {tree}"
    assert cached_skill.read_bytes() == PLUGIN_SKILL.read_bytes()
    assert (cached_root / ".claude-plugin" / "plugin.json").exists()


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin")
