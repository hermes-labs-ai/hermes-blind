# Contributing to hermes-blind

Thanks for looking. Small tool, narrow scope — here's how to help without
breaking it.

## Scope

This project is a ~40-token language scaffold and a parser for the model's
disclosure line. That's it. It stays small on purpose.

Accepted:

- New scaffold variants (see below)
- Empirical test results (Phase 4 ablation data)
- Documentation corrections
- Bug fixes in `extract_disclosure` response-shape handling
- CI improvements

Not accepted:

- New dependencies. Stdlib-only is part of the tool's shape.
- A CLI. The library is small enough to import; a CLI is framework-adjacent.
- Generation debiasing scope. That's a different problem.
- Productization beyond trust/discoverability/release layer.

## Dev setup

```bash
git clone https://github.com/hermes-labs-ai/hermes-blind
cd hermes-blind
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

## Adding a variant

Variants live in `VARIANTS` (`src/hermes_blind/scaffold.py`). Any new variant
must:

- Preserve the caller's prompt at the tail unchanged
- End with `\n\n` (separates scaffold from prompt)
- Fit the strict length ordering: `null < micro < short < v1 < full` (or
  extend the ordering with a clearly documented new position)
- Ship with a corresponding unit test in `tests/test_scaffold.py`
- Update `CHANGELOG.md` in the same PR

The length-ordering invariant is tested. If your variant breaks it, the PR
fails CI.

## Reporting a bug

Open an issue with:

- Python version
- Variant used
- Minimum reproduction: `wrap(prompt, variant="...")` output
- Expected vs. actual

## Reporting empirical data

If you run the Phase 4 ablation (variance reduction study) on your own
corpus, please file an issue with:

- backend(s) tested
- target corpus size and domain
- variance before/after per variant
- cross-model std if applicable

This is the data we need most. v0.0.x stays experimental until the effect
is measured independently.

## Code style

- `ruff` with default rules
- Type hints on public functions
- Docstrings on everything in `__all__`

## License

By contributing, you agree your contributions are licensed under the project's
MIT License.
