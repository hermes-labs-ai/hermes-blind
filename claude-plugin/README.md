# Hermes Blind Claude Code plugin

Hermes Blind re-anchors long Claude Code or Codex sessions to their original
user goal. The included `hermes-blind` skill reads only local session logs,
writes an inspectable recovery file, makes no model calls, and sends no network
requests.

This directory is the portable plugin package used by external Claude Code
catalogs. It contains the same `hermes-blind` skill as the repository-root
package.

## Install locally

Clone the repository, then point Claude Code at this package directory:

```bash
git clone https://github.com/hermes-labs-ai/hermes-blind
cd hermes-blind
claude --plugin-dir ./claude-plugin
```

Or install Hermes Blind from its source marketplace:

```bash
claude plugin marketplace add hermes-labs-ai/hermes-blind
claude plugin install hermes-blind@hermes-blind
```

In the interactive Claude Code prompt, the equivalent install command is:

```text
/plugin install hermes-blind@hermes-blind
```

The skill uses the `hermes-blind` CLI. If it is not already available, the
skill prefers the version-pinned, zero-install runner:

```bash
uvx hermes-blind==0.2.0 --help
```

## Use

Ask Claude Code to re-anchor a drifting or long-running session. When the
skill applies, it writes `recovery.md` only after an explicit request and will
not overwrite an existing file unless `--force` is explicitly requested.

For the command-line package, evidence notes, and full project documentation,
see the [repository README](https://github.com/hermes-labs-ai/hermes-blind).

## License

[MIT](../LICENSE)
