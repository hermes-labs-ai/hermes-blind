"""Tests for the Codex CLI and Gemini CLI install surfaces.

The repository root is one plugin: `skills/hermes-blind/SKILL.md` plus a
manifest per host format that points at it —

  plugin.json                        portable Agent Plugins 1.0.0 manifest
                                     (read by Codex CLI)
  .agents/plugins/marketplace.json   Codex repo marketplace, source "./"
  gemini-extension.json              Gemini CLI extension manifest
  .claude-plugin/                    Claude Code (test_plugin_manifest.py,
                                     test_marketplace.py)

None of them carries its own copy of the skill, and every identity field
must match pyproject.toml so the manifests cannot drift from the release.
The live tests install into an isolated HOME and read the result back.
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
PORTABLE_MANIFEST = ROOT / "plugin.json"
CODEX_MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
GEMINI_MANIFEST = ROOT / "gemini-extension.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
PLUGIN_SKILL = ROOT / "skills" / "hermes-blind" / "SKILL.md"
PYPROJECT = ROOT / "pyproject.toml"
SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PORTABLE_KEYS = {
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pyproject_field(name: str) -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(rf'^{re.escape(name)}\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert match, f"{name} not found in pyproject.toml"
    return match.group(1)


def test_portable_manifest_follows_agent_plugins_schema():
    manifest = _json(PORTABLE_MANIFEST)
    assert manifest["$schema"] == SCHEMA_ID
    assert NAME_PATTERN.match(manifest["name"]) and len(manifest["name"]) <= 64
    assert set(manifest) <= PORTABLE_KEYS, set(manifest) - PORTABLE_KEYS
    assert set(manifest.get("author", {})) <= {"name", "email", "url"}


def test_every_manifest_identity_matches_pyproject():
    name, version = _pyproject_field("name"), _pyproject_field("version")
    description = _pyproject_field("description")
    for path in (PORTABLE_MANIFEST, GEMINI_MANIFEST, CLAUDE_MANIFEST):
        manifest = _json(path)
        assert manifest["name"] == name, path
        assert manifest["version"] == version, path
        assert manifest["description"] == description, path
    claude = _json(CLAUDE_MANIFEST)
    portable = _json(PORTABLE_MANIFEST)
    for key in ("author", "homepage", "repository", "license"):
        assert portable[key] == claude[key], key


def test_codex_marketplace_resolves_to_the_repository_root():
    """One plugin: the Codex entry must name the root, not a second copy."""
    marketplace = _json(CODEX_MARKETPLACE)
    (entry,) = marketplace["plugins"]
    assert marketplace["name"] == entry["name"] == _pyproject_field("name")
    assert entry["source"] == {"source": "local", "path": "./"}
    assert (CODEX_MARKETPLACE.parents[2] / entry["source"]["path"]).resolve() == ROOT.resolve()
    assert entry["policy"]["installation"] in {"AVAILABLE", "INSTALLED_BY_DEFAULT"}
    assert entry["policy"]["authentication"] in {"ON_INSTALL", "ON_USE"}
    assert entry["category"]
    assert "version" not in entry


def test_no_host_ships_its_own_skill_copy():
    """Codex and Gemini both load skills/ from the root; nothing else may fork it."""
    assert PLUGIN_SKILL.is_file()
    for extra in (ROOT / ".agents" / "skills", ROOT / ".gemini", ROOT / ".codex-plugin"):
        assert not extra.exists(), f"{extra} would be a second, driftable skill surface"


def test_llms_gemini_install_pins_a_ref():
    """An unpinned GitHub install takes the latest release, which may predate the manifest.

    `gemini extensions install <github-url>` prefers the latest GitHub release
    archive; v0.3.0 has no gemini-extension.json, so the unpinned command fails
    with `Configuration file not found` even though main is installable.
    """
    pattern = re.compile(r"gemini extensions install https://github\.com/hermes-labs-ai/hermes-blind[^\n`]*")
    for doc in (ROOT / "llms.txt",):
        commands = pattern.findall(doc.read_text(encoding="utf-8"))
        assert commands, f"{doc.name} no longer documents the Gemini install"
        for command in commands:
            assert "--ref " in command, f"{doc.name}: {command!r} must pass --ref"


def _package(tmp_path: Path) -> Path:
    """The tracked install surface, without local build or venv state."""
    pkg = tmp_path / "hermes-blind"
    pkg.mkdir()
    for rel in ("plugin.json", "gemini-extension.json"):
        shutil.copy2(ROOT / rel, pkg / rel)
    for rel in (".agents", ".claude-plugin", "skills"):
        shutil.copytree(ROOT / rel, pkg / rel)
    return pkg


def _run(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, env=env, timeout=120)


@pytest.mark.skipif(shutil.which("codex") is None, reason="codex CLI not installed")
def test_codex_marketplace_install_reads_back_the_skill(tmp_path):
    pkg = _package(tmp_path)
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    env = {"HOME": str(home), "CODEX_HOME": str(home / ".codex"),
           "PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    add = _run(["codex", "plugin", "marketplace", "add", str(pkg)], env)
    assert add.returncode == 0, f"{add.stdout}\n{add.stderr}"
    install = _run(["codex", "plugin", "add", "hermes-blind@hermes-blind"], env)
    assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"

    listed = _run(["codex", "plugin", "list"], env)
    line = next((ln for ln in listed.stdout.splitlines()
                 if ln.startswith("hermes-blind@hermes-blind")), "")
    assert "installed, enabled" in line and _pyproject_field("version") in line, listed.stdout
    cached = (home / ".codex" / "plugins" / "cache" / "hermes-blind" / "hermes-blind"
              / _pyproject_field("version") / "skills" / "hermes-blind" / "SKILL.md")
    assert cached.read_bytes() == PLUGIN_SKILL.read_bytes()


@pytest.mark.skipif(shutil.which("gemini") is None, reason="gemini CLI not installed")
def test_gemini_extension_install_discovers_the_skill(tmp_path):
    pkg = _package(tmp_path)
    home = tmp_path / "home"
    (home / ".gemini").mkdir(parents=True)
    # Listing is local, but the CLI refuses to start without an auth method.
    (home / ".gemini" / "settings.json").write_text(
        '{"security":{"auth":{"selectedType":"gemini-api-key"}}}', encoding="utf-8")
    env = {"HOME": str(home), "GEMINI_API_KEY": "placeholder-not-a-key",
           "PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    install = _run(["gemini", "extensions", "install", str(pkg), "--consent"], env)
    assert install.returncode == 0, f"{install.stdout}\n{install.stderr}"
    skills = _run(["gemini", "skills", "list"], env)
    assert skills.returncode == 0, skills.stderr
    installed = home / ".gemini" / "extensions" / "hermes-blind" / "skills" / "hermes-blind" / "SKILL.md"
    listing = skills.stdout + skills.stderr  # the CLI prints the listing to stderr
    assert str(installed) in listing, listing
    assert installed.read_bytes() == PLUGIN_SKILL.read_bytes()
