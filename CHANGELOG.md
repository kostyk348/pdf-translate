# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries are derived from `git log` only.

## [Unreleased]

### Changed

- CI: the PyPI publishing job was dropped — the project is a single script with no
  `pyproject.toml`, so there is nothing to publish (`cf89d43` added a build+publish job,
  `38ec8a4` removed it two days later).
- CI: `workflow_dispatch` added for manual runs (`5cdee0e`).

### Added

- README badges and formatting pass (`d07e221`).

No source code changed after v0.1.0: `git diff --stat v0.1.0..HEAD` touches only
`.github/workflows/ci.yml` and `README.md`.

## [0.1.0] — 2026-07-10

Tag `v0.1.0` points at `923b3ef` (2026-07-10); the GitHub release was published
2026-10-16.

### Added

- **Single-file pipeline** `pdf-translate.py` — `SENSE` (PyMuPDF text/line/span
  extraction with bbox, rotation, font, size) → `FACT` (filter, dedupe, canonical order)
  → `LOGIC` (DeepLX per-line translation) → `CAUSALITY` (redact original text with
  `fill=None`, insert the translation at the same baseline) → `VERIFIER` (hash-chained
  audit log) (`43b05a1`).
- **Self-bootstrapping**: the script creates its own `.venv` and installs PyMuPDF +
  Pillow on first run, so there is no manual `pip install` step (`43b05a1`).
- **Windows ports**: `pdf-translate_win.py` (Google Translate backend) and
  `pdf-translate_win_deeplx.py` (DeepLX with a Google fallback) (`2a78db8`).
- **JSON workflow**: `--export-json` / `--import-json` / `--translate-json` for offline or
  external translation, with the full per-line metadata kept in the file (`17d392d`).
- **Tests**: `tests/test_pipeline.py` — 51 pure-function tests that never touch DeepLX
  (`6dc8406`).
- **CI**: GitHub Actions lint + test workflow, and its badge in the README (`54c726b`,
  `8a77333`).
- **Demo material**: MSP430-UIF manual, Chinese original and Russian translation, plus a
  GIF of the run (`ab78016`, `dc26f97`).
- `LICENSE` (MIT), `requirements.txt`, README with badges and a project-structure tree
  (`1b20557`); Open Graph preview image (`b86fac5`).

### Fixed

- Text overflow: the font is scaled down to fit the original bbox instead of running over
  neighbouring drawing elements (`eaf75d0`).
- Text overlap: text-extent heuristic calibrated for Liberation Sans Cyrillic, table-cell
  boundaries detected from grid lines, `MIN_FONT_SIZE` lowered to 5.0, 5 pt safety margin
  in the overflow guard (`ac0fbd9`).
- Integer colour value was mishandled when inserting text (`dc26f97`).

### Changed

- Windows and Linux usage instructions written out separately, including the
  `python pdf-translate.py` form needed on Windows (`923b3ef`).
- A failing CI workflow was removed and re-added in a working form on the same day
  (`8bdc8b5` → `54c726b`).

### Known limitations at v0.1.0

- Translation requires a running DeepLX server on `127.0.0.1:1188`. The script starts one
  if `.venv/bin/deeplx` exists (or a `deeplx` binary is on `PATH`) but does **not**
  download it; if neither is present the pipeline stops with
  `FileNotFoundError: 'deeplx'`, even though the README describes the download as an
  automatic first-run step.
- DeepLX talks to DeepL's free front-end; on a rate-limited or blocked IP every line comes
  back `HTTP 429` and the output PDF keeps the original text.

[Unreleased]: https://github.com/kostyk348/pdf-translate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kostyk348/pdf-translate/releases/tag/v0.1.0
