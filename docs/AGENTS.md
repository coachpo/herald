# docs/AGENTS.md

The [README index](../README.md#docs) maps document ownership. Describe implemented behavior from code and tests; do not infer deployment or retention obligations. Keep English/Chinese READMEs consistent and link detailed operational facts instead of duplicating them.

`openapi.yaml` is generated from `backend.app.create_app().openapi()` (JSON is valid YAML). Use a temporary `HERALD_DATA_DIR` for generation and never hand-edit it. Token/key values must never appear in examples or generated artifacts.

For prose edits, inspect source facts, relative links/anchors, and `git diff --check`. Do not run unrelated full suites.
