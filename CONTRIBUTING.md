# Contributing to hermes-blind

Thanks for helping keep this package small, local, and honest.

## Scope

Accepted:

- parser and goal-extraction fixes;
- prompt-scaffold variants with explicit invariants;
- documentation and privacy improvements;
- deterministic tests and package/release hardening;
- reproducible empirical results with bounded claims.

Out of scope for the public runtime:

- non-standard-library runtime dependencies;
- automatic session monitoring or model invocation;
- internal research harnesses tied to sibling repositories;
- claims of bias reduction or drift recovery without controlled evidence.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests
pytest -q
python -m build
twine check dist/*
```

Changes to parsing, extraction, variants, or output shape require regression
tests. Preserve the caller's prompt, keep `null` an exact no-op, and do not
emit absolute session paths by default.

## Reporting a bug

Open an issue with the Python version, exact command or API call, a minimal
sanitized input, and expected versus actual output.

## License

Contributions are licensed under the project's MIT License.
