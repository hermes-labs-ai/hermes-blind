"""Tests for the repository-hosted Claude Code marketplace surface.

`.claude-plugin/marketplace.json` makes this repo installable with
`claude plugin marketplace add hermes-labs-ai/hermes-blind` +
`claude plugin install hermes-blind@hermes-blind`, on top of the existing
`.claude-plugin/plugin.json` root plugin package (test_plugin_manifest.py)
used for local `--plugin-dir .` loading. The marketplace entry must resolve
to that same plugin — no second copy, no hand-maintained version that can
drift from pyproject.toml/plugin.json.

`claude-plugin/` is the third surface: a subdirectory package that an
*external* catalog (e.g. hermes-labs-ai/claude-plugins) can reach with a
`git-subdir` source. It exists because no cross-repo source type in Claude
Code 2.1.x can install a plugin that lives at a repository root — see
`test_cross_repo_subdir_install_delivers_the_skill` for the round trip and
`test_root_path_subdir_source_drops_subdirectories` for the failure it
replaces. Its files must stay byte-identical to the root package.
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
SUBDIR_PACKAGE = ROOT / "claude-plugin"
SUBDIR_MANIFEST = SUBDIR_PACKAGE / ".claude-plugin" / "plugin.json"
SUBDIR_SKILL = SUBDIR_PACKAGE / "skills" / "hermes-blind" / "SKILL.md"


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

    This repo-hosted marketplace resolves `source` relative to the marketplace
    itself, so the repo root — where `.claude-plugin/plugin.json` already
    lives — is the plugin. A cross-repo catalog cannot use this entry (see
    `claude-plugin/` and the cross-repo tests below); that is a separate
    package, not a change to this one.
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


# --- cross-repo catalog surface (claude-plugin/) --------------------------
#
# An external catalog such as hermes-labs-ai/claude-plugins cannot reuse the
# repo-root entry above: it has to name this repository by URL, and in Claude
# Code 2.1.x every cross-repo source type that can reach a *root*-level plugin
# is unusable —
#
#   {"source": "github", "repo": ...}            clones over git@github.com
#                                                (no HTTPS fallback), so it
#                                                fails outright without SSH
#                                                credentials;
#   {"source": "git-subdir", "path": "."}        installs, but copies only the
#                                                top-level *files* of the repo
#                                                and drops every subdirectory,
#                                                including skills/;
#   {"source": "git", ...}                       unsupported source type;
#   {"source": "git-subdir", "path": ""}         schema-invalid.
#
# Only a `git-subdir` source naming a real subdirectory copies a nested tree
# intact, so the plugin is also published as the `claude-plugin/` package.
#
# `claude plugin install` exits 0 even when the install fails, so these tests
# assert on the resulting cache contents, never on a return code.


def _git(args: list[str], cwd: Path) -> None:
    env = {
        "PATH": _path_env(),
        "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                   capture_output=True, text=True)


def _origin_repo(tmp_path: Path) -> Path:
    """A throwaway git repo holding this repo's plugin surfaces on `main`.

    Built from the working tree rather than cloned from ROOT so the test
    exercises the files as they stand, committed or not.
    """
    origin = tmp_path / "origin"
    (origin / ".claude-plugin").mkdir(parents=True)
    shutil.copy2(PLUGIN_MANIFEST, origin / ".claude-plugin" / "plugin.json")
    shutil.copytree(ROOT / "skills", origin / "skills")
    if SUBDIR_PACKAGE.exists():
        shutil.copytree(SUBDIR_PACKAGE, origin / "claude-plugin")
    _git(["init", "-b", "main"], origin)
    _git(["add", "-A"], origin)
    _git(["commit", "-m", "plugin surfaces"], origin)
    return origin


def _install_from_subdir(tmp_path: Path, name: str, origin: Path, path: str) -> Path:
    """Install `origin` at `path` through a local catalog; return the cache root."""
    catalog = tmp_path / f"catalog-{name}"
    (catalog / ".claude-plugin").mkdir(parents=True)
    (catalog / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": name,
        "description": "cross-repo source regression harness",
        "owner": {"name": "test", "email": "test@example.com"},
        "plugins": [{
            "name": "hermes-blind",
            "description": _plugin()["description"],
            "version": _plugin()["version"],
            "source": {
                "source": "git-subdir",
                "url": f"file://{origin}",
                "path": path,
                "ref": "main",
            },
        }],
    }), encoding="utf-8")

    config_dir = tmp_path / f"config-{name}"
    config_dir.mkdir()
    home = tmp_path / f"home-{name}"
    home.mkdir()
    env = {"CLAUDE_CONFIG_DIR": str(config_dir), "HOME": str(home), "PATH": _path_env()}

    add = subprocess.run(["claude", "plugin", "marketplace", "add", str(catalog)],
                         capture_output=True, text=True, check=False, env=env)
    assert add.returncode == 0, f"marketplace add failed:\n{add.stdout}\n{add.stderr}"
    subprocess.run(["claude", "plugin", "install", f"hermes-blind@{name}"],
                   capture_output=True, text=True, check=False, env=env)
    return config_dir / "plugins" / "cache" / name / "hermes-blind" / _plugin()["version"]


def test_cross_repo_subdir_package_mirrors_the_root_package():
    """`claude-plugin/` is a copy, never a fork.

    Same rule as the root/`.claude` SKILL.md pair in test_plugin_manifest.py:
    a second copy is only safe while it cannot drift.
    """
    assert SUBDIR_MANIFEST.read_bytes() == PLUGIN_MANIFEST.read_bytes(), (
        f"{SUBDIR_MANIFEST} has drifted from {PLUGIN_MANIFEST}"
    )
    assert SUBDIR_SKILL.read_bytes() == PLUGIN_SKILL.read_bytes(), (
        f"{SUBDIR_SKILL} has drifted from {PLUGIN_SKILL}"
    )


def test_cross_repo_subdir_package_is_self_contained():
    """Everything the cross-repo package needs must live under it.

    A `git-subdir` install copies only this directory, so a reference that
    climbs out of it would resolve in the checkout and be missing in the cache.
    """
    assert SUBDIR_SKILL.is_file()
    for path in SUBDIR_PACKAGE.rglob("*"):
        assert not path.is_symlink(), f"{path} is a symlink; it would dangle in the plugin cache"


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_cross_repo_subdir_package_validates_strict():
    result = subprocess.run(
        ["claude", "plugin", "validate", str(SUBDIR_MANIFEST), "--strict"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"claude plugin validate --strict failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_cross_repo_subdir_install_delivers_the_skill(tmp_path):
    """The catalog-facing round trip: install by URL + subdir, get the skill.

    Fails on the pre-`claude-plugin/` layout, where the only thing an external
    catalog could name was the repository root.
    """
    origin = _origin_repo(tmp_path)
    cached = _install_from_subdir(tmp_path, "subdir", origin, "claude-plugin")

    cached_skill = cached / "skills" / "hermes-blind" / "SKILL.md"
    tree = sorted(str(p.relative_to(cached)) for p in cached.rglob("*")) if cached.exists() else "cache root missing"
    assert cached_skill.is_file(), f"expected cached skill at {cached_skill}; cache tree: {tree}"
    assert cached_skill.read_bytes() == PLUGIN_SKILL.read_bytes()
    assert (cached / ".claude-plugin" / "plugin.json").is_file(), f"cache tree: {tree}"


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_root_path_subdir_source_drops_subdirectories(tmp_path):
    """Why `claude-plugin/` exists: a root-path source silently loses skills/.

    `path: "."` reports a successful install and caches the repository's
    top-level files, but no subdirectory — so the plugin loads with no skill.
    If this ever starts passing, Claude Code has gained working root-path
    support: retire `claude-plugin/` only after the external catalog that
    points at it has been moved off it.
    """
    origin = _origin_repo(tmp_path)
    cached = _install_from_subdir(tmp_path, "rootpath", origin, ".")

    assert cached.is_dir(), "root-path install produced no cache directory at all"
    assert (cached / ".claude-plugin" / "plugin.json").exists() is False
    assert (cached / "skills" / "hermes-blind" / "SKILL.md").exists() is False, (
        "root-path git-subdir sources now copy subdirectories; see this test's docstring"
    )
