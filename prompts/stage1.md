# POlyglott Stage 1: PO Scanning and CSV Export

## Overview

Create a Python CLI tool called POlyglott that parses gettext PO files and exports them to CSV for translation workflow management. This stage delivers the MVP: a working `scan` subcommand that handles single and multi-file PO-to-CSV conversion.

## Scope — Stage 1 ONLY

**In scope:**

- Project scaffolding (package structure, pyproject.toml, dependencies)
- PO file parsing using `polib`
- CSV export using `pandas`
- CLI with `scan` subcommand using `argparse`
- Multi-file processing with glob patterns (`--include`, `--exclude`)
- Configurable sorting (`--sort-by`)
- Error handling for missing/malformed files
- Comprehensive test suite
- Project documentation (README, LICENSE, CHANGELOG)

**Out of scope (future stages):**

- Lint subcommand (Stage 2)
- Glossary support (Stage 2)
- Context inference (Stage 3)
- Master CSV workflow (Stage 4)
- DeepL integration (Stage 5)
- CSV → PO import (future)

## Project Structure

```
POlyglott/
├── .gitignore
├── .claudeignore
├── pyproject.toml
├── LICENSE.md
├── README.md
├── CHANGELOG.md
├── CLAUDE.md                  # Already exists — do not recreate
├── AI_DEVELOPMENT.md          # Already exists — do not recreate
├── prompts/                   # Already exists — do not modify
│   ├── stage1.md
│   ├── stage2.md
│   ├── stage3.md
│   ├── stage4.md
│   └── stage5.md
├── src/
│   └── polyglott/
│       ├── __init__.py        # __version__ = "0.1.0"
│       ├── __main__.py        # python -m polyglott support
│       ├── cli.py             # CLI entry point
│       ├── parser.py          # PO file parsing
│       └── exporter.py        # CSV export
└── tests/
    ├── __init__.py
    ├── test_parser.py
    ├── test_exporter.py
    └── fixtures/              # Test PO files
```

## Configuration

### pyproject.toml

```toml
[project]
name = "polyglott"
version = "0.1.0"
description = "Translation workflow tools for PO files"
license = { text = "MIT" }
requires-python = ">=3.10"
dependencies = [
    "polib",
    "pandas",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "bump-my-version",
]

[project.scripts]
polyglott = "polyglott.cli:main"
```

Include `bump-my-version` configuration targeting `pyproject.toml` and `src/polyglott/__init__.py`.

### .gitignore

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
*.egg
dist/
build/

# Virtual environments
.venv/

# Testing / coverage
.pytest_cache/
.coverage
.coverage.*
htmlcov/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
```

### .claudeignore

```
# Build artifacts
.venv/
dist/
build/
*.egg-info/
__pycache__/

# Test output
.pytest_cache/
htmlcov/
.coverage

# Prevent contamination from company-specific projects
**/GRAPE/**
**/grape/**
**/Softwerk/**
**/softwerk/**
```

## CLI Design

### Usage

```bash
# Single file scan
polyglott scan locale/de/LC_MESSAGES/django.po -o output.csv

# Multi-file with glob patterns
polyglott scan --include "locale/**/*.po" -o output.csv

# Exclude patterns
polyglott scan --include "**/*.po" --exclude "**/test_*.po" -o output.csv

# Custom sorting
polyglott scan --include "*.po" --sort-by fuzzy -o output.csv

# Output to stdout (default when no -o)
polyglott scan locale/de/LC_MESSAGES/django.po

# Version
polyglott --version
```

### Arguments

```
polyglott scan [OPTIONS] [FILE]

Arguments:
  FILE                    Single .po file to scan (optional if --include used)

Options:
  -o, --output FILE       Output CSV file (default: stdout)
  --include PATTERN       Glob pattern(s) for .po files (repeatable)
  --exclude PATTERN       Glob pattern(s) to exclude (repeatable)
  --sort-by FIELD         Sort output by field (msgid, source_file, fuzzy, msgstr)
```

### Behavior

- If a positional `FILE` is given, scan that single file
- If `--include` is given, expand glob patterns and scan all matches
- `FILE` and `--include` are mutually exclusive
- If `--exclude` is given, filter out matching files from the include set
- If no output file specified, write CSV to stdout
- Display statistics after scan: total entries, untranslated, fuzzy, plurals

## CSV Export Schema

### Single-file mode

| Column                | Description                        |
|-----------------------|------------------------------------|
| `msgid`               | Source message string              |
| `msgstr`              | Translated message string          |
| `msgctxt`             | Message context (if present)       |
| `extracted_comments`  | Comments from source code (`#.`)   |
| `translator_comments` | Translator-added comments (`#`)    |
| `references`          | Source code locations (`#:`)       |
| `fuzzy`               | Boolean — entry flagged as fuzzy   |
| `obsolete`            | Boolean — entry is obsolete (`#~`) |
| `is_plural`           | Boolean — entry has plural forms   |
| `plural_index`        | Plural form index (if applicable)  |

### Multi-file mode

Same columns, with `source_file` prepended as the first column.

### Encoding

UTF-8. Full Unicode support (emoji, CJK, Arabic, German umlauts).

## Implementation Notes

### Parser module (`parser.py`)

- Use `polib` to parse PO files
- Extract all entry metadata: msgid, msgstr, msgctxt, comments, references, flags
- Handle plural forms (msgid_plural, msgstr[0], msgstr[1], etc.)
- Handle obsolete entries
- Return structured data suitable for DataFrame conversion
- Statistics collection: total, untranslated, fuzzy, plural counts

### Exporter module (`exporter.py`)

- Accept parsed entry data
- Build pandas DataFrame
- Handle single-file vs multi-file column schemas
- Sort by specified field
- Export to CSV with proper quoting and UTF-8 encoding

### CLI module (`cli.py`)

- argparse with `scan` subcommand
- File discovery: glob expansion, exclude filtering, tilde expansion, absolute paths
- Validation: file exists, valid PO format
- Statistics display after processing
- Proper exit codes: 0 success, 1 error

## Test Suite

### Test fixtures

Create test PO files in `tests/fixtures/`:

- `simple.po` — basic entries with translations
- `complex.po` — plurals, context, comments, fuzzy flags, obsolete entries
- `unicode.po` — emoji, CJK characters, Arabic, German umlauts
- `empty.po` — valid PO file with no entries
- `malformed.po` — for error handling tests

### Parser tests (`test_parser.py`)

- Parse simple PO file — correct entry count
- Extract msgid and msgstr
- Extract msgctxt
- Extract extracted comments and translator comments
- Extract source references
- Detect fuzzy flag
- Detect obsolete entries
- Handle plural forms
- Handle Unicode characters
- Statistics: correct counts for total, untranslated, fuzzy, plurals
- Error: missing file raises appropriate error
- Error: malformed PO file handled gracefully

### Exporter tests (`test_exporter.py`)

- Single-file CSV has correct columns (no source_file)
- Multi-file CSV has source_file as first column
- UTF-8 encoding preserved
- Proper CSV escaping (quotes, commas, newlines in values)
- Sort by msgid (default)
- Sort by fuzzy
- Sort by source_file (multi-file mode)
- Empty DataFrame produces valid CSV with headers only
- Plural entries export correctly

### Integration tests

- CLI: `polyglott scan <file> -o output.csv` produces valid CSV
- CLI: `--include` glob pattern expands correctly
- CLI: `--exclude` filters files
- CLI: `--sort-by` changes output order
- CLI: missing file produces error message and exit code 1
- CLI: `--version` shows version
- CLI: stdout output when no `-o` specified

## Documentation

### README.md

Create a public-facing README following GitHub best practices:

- Project name and one-line description
- Badges (if appropriate): Python version, license
- Installation: `pip install polyglott` (or `pip install -e ".[dev]"` for development)
- Quick start with 2-3 usage examples
- Full CLI reference for `scan`
- CSV output format description
- Roadmap overview (Stages 1-5, brief one-liner per stage)
- Contributing section (brief, pointing to development setup)
- License: MIT

**Keep it concise.** This is a CLI tool, not a framework.

### LICENSE.md

MIT License.

### CHANGELOG.md

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - YYYY-MM-DD

### Added

- PO file parsing with full gettext format support
- CSV export with UTF-8 Unicode support
- Multi-file processing with glob patterns
- Configurable sorting (msgid, source_file, fuzzy, msgstr)
- Comprehensive error handling and statistics display
```

## Version

This is Stage 1. After all tests pass and documentation is complete:

- Version is `0.1.0` (set from the start in pyproject.toml and __init__.py)
- No intermediate version bumps during development

## Git Workflow

See `CLAUDE.md` for the full workflow. For this stage:

1. Work on `feature/scan` branch
2. Regular commits with good messages
3. When complete: merge `--no-ff` to `develop`
4. Bump version on develop (should already be 0.1.0 from scaffolding)
5. Update CHANGELOG with date
6. Merge `--no-ff` to `main`
7. Tag: `git tag -a v0.1.0 -m "MVP: PO file scanning and CSV export"`

## Constraints

- No dependencies beyond `polib`, `pandas` (runtime) and `pytest`, `bump-my-version` (dev)
- Python 3.10+
- Generic OSS tool — no company-specific references
- All tests must pass before considering Stage 1 complete
