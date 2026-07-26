# Chronology Builder

A local, offline-first tool that helps a nurse paralegal build cited medical chronologies from case
records for medical malpractice litigation. Everything — document extraction, the LLM (via
[Ollama](https://ollama.com)), and the review UI — runs entirely on one machine. Nothing leaves it.

**Prototype only.** Do not use with real case files or PHI until firm IT/compliance has formally
approved this project (see [`PRODUCT_DEFINITION.md`](PRODUCT_DEFINITION.md) §7/§9).

## Getting Started

Download the latest installer from this repo's [Releases page](../../releases/latest) and run it —
it bundles Ollama and the AI model, and walks through the rest on first launch. See
[`DESKTOP_PACKAGING.md`](DESKTOP_PACKAGING.md) for what that first-run step actually does and what's
still Windows-unverified.

## What's in this repo

- `webapp/` — the Flask backend + browser UI (chronology builder, case mode, review workflow, export).
- `electron/` — the desktop shell (packaging, auto-update, the bundled Ollama/model first-run flow).
- `prompts/` — the LLM prompt templates.
- `scripts/` — one-off build/dev tooling (icon generation, backend freezing, version bumps).
- `testing/` — the Playwright-based automated test suite.
- `sample_data/` — synthetic test fixtures only. No real case data belongs in this repo, ever.

## Key docs

- [`PRODUCT_DEFINITION.md`](PRODUCT_DEFINITION.md) — the actual product/architecture/rollout plan.
- [`TOWER_SETUP.md`](TOWER_SETUP.md) — the real target deployment (an air-gapped dedicated workstation).
- [`DESKTOP_PACKAGING.md`](DESKTOP_PACKAGING.md) — how the installer is built and what's verified.
- [`TEST_RESULTS.md`](TEST_RESULTS.md) — a running log of what's been built, tested, and found.
- [`TESTING_PLAN.md`](TESTING_PLAN.md) — local dev environment setup, including one-time git hooks setup.
