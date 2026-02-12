# POlyglott Stage 5.1: CLI Harmonization

## Overview

Harmonize CLI flags across `import` and `export` subcommands. Stage 5 introduced these commands with the master CSV as a positional argument and incomplete flag coverage. Stage 5.1 revives `--master` as a named flag, adds missing `--include` and `--sort-by` flags, and refactors shared argument definitions into parent parsers to prevent future omissions.

## Scope — Stage 5.1 ONLY

**In scope:**

- Revive `--master` flag for `import` and `export` (replaces positional master CSV)
- Add `--include` and `--sort-by` to `import`
- Add `--include` and `--sort-by` to `export`
- Refactor `cli.py` to use argparse parent parsers for shared flags
- Shared `resolve_po_files()` helper for PO file collection
- Comprehensive test suite for flag combinations
- Documentation updates

**Out of scope:**

- DeepL integration (Stage 6)
- New subcommands
- Behavioral changes to existing master CSV logic

## Problem Statement

After Stage 5:

```bash
# import — missing --include, --sort-by; master CSV is awkward positional
polyglott import master-de.csv --include "src/**/de/LC_MESSAGES/django.po"
# → error: unrecognized arguments: --include --sort-by

# export — missing --include, --sort-by
polyglott export master-de.csv --include "src/**/de/LC_MESSAGES/django.po"
# → error: unrecognized arguments: --include

# Two positionals create ambiguity
polyglott import master-de.csv locale/de/LC_MESSAGES/django.po
# → which is the master? which are PO files?
```

## CLI Changes

### Before (Stage 5.0)

```bash
# master CSV as first positional, PO files as remaining positionals
polyglott import polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po
polyglott export polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po
```

### After (Stage 5.1)

```bash
# --master flag, PO files via positionals and/or --include
polyglott import \
    --master polyglott-accepted-de.csv \
    --include "locale/de/LC_MESSAGES/*.po"

polyglott import \
    --master polyglott-accepted-es.csv \
    --include "../src/**/es/LC_MESSAGES/django.po" \
    --exclude "../src/help/**/es/LC_MESSAGES/django.po" \
    --exclude "../src/pages/**/es/LC_MESSAGES/django.po" \
    --glossary glossary-es.yaml \
    --context-rules polyglott-context.yaml \
    --sort-by msgid

polyglott export \
    --master polyglott-accepted-de.csv \
    --include "locale/de/LC_MESSAGES/*.po" \
    --status accepted \
    -v
```

### PO file input: positionals + `--include`

Both paths are valid and combine:

```bash
# --include only (recursive globs)
polyglott import \
    --master master-de.csv \
    --include "src/**/de/LC_MESSAGES/django.po"

# Positionals only (shell-expanded)
polyglott import \
    --master master-de.csv \
    locale/de/LC_MESSAGES/django.po

# Combined — union of both
polyglott import \
    --master master-de.csv \
    --include "apps/**/de/LC_MESSAGES/django.po" \
    locale/de/LC_MESSAGES/django.po

# --exclude removes from the union
polyglott import \
    --master master-de.csv \
    --include "src/**/de/LC_MESSAGES/django.po" \
    --exclude "src/legacy/**"
```

At least one PO file must result from positionals, `--include`, or both. If none remain after `--exclude`, exit with error.

## Flag Inventory

### Current flags by subcommand (Stage 5.0)

| Flag               | `scan` | `import` | `export` | `lint` |
|--------------------|--------|----------|----------|--------|
| `--include`        | ✓      | ✗        | ✗        | ✓      |
| `--exclude`        | ✓      | ✓        | ✓        | ✓      |
| `--sort-by`        | ✓      | ✗        | ✗        | —      |
| `--master`         | —      | (pos.)   | (pos.)   | —      |
| `--glossary`       | ✓      | ✓        | —        | ✓      |
| `--context-rules`  | ✓      | ✓        | —        | —      |
| `--preset`         | ✓      | ✓        | —        | —      |
| `-o` / `--output`  | ✓      | —        | —        | —      |
| `--lang`           | —      | ✓        | ✓        | —      |
| `--status`         | —      | —        | ✓        | —      |
| `--dry-run`        | —      | —        | ✓        | —      |
| `-v` / `--verbose` | —      | —        | ✓        | —      |

### Target flags by subcommand (Stage 5.1)

| Flag               | `scan` | `import` | `export` | `lint` |
|--------------------|--------|----------|----------|--------|
| `--include`        | ✓      | ✓        | ✓        | ✓      |
| `--exclude`        | ✓      | ✓        | ✓        | ✓      |
| `--sort-by`        | ✓      | ✓        | ✓        | —      |
| `--master`         | —      | ✓        | ✓        | —      |
| `--glossary`       | ✓      | ✓        | —        | ✓      |
| `--context-rules`  | ✓      | ✓        | —        | —      |
| `--preset`         | ✓      | ✓        | —        | —      |
| `-o` / `--output`  | ✓      | —        | —        | —      |
| `--lang`           | —      | ✓        | ✓        | —      |
| `--status`         | —      | —        | ✓        | —      |
| `--dry-run`        | —      | —        | ✓        | —      |
| `-v` / `--verbose` | —      | —        | ✓        | —      |

Changes from 5.0: `--include` added to `import` and `export`. `--sort-by` added to `import` and `export`. Master CSV from positional to `--master` flag on `import` and `export`.

## Parent Parser Design

### Shared argument groups

```python
# PO file input — used by scan, import, export, lint
po_input_parser = argparse.ArgumentParser(add_help=False)
po_input_parser.add_argument('po_files', nargs='*', help='PO files (positional)')
po_input_parser.add_argument('--include', action='append', help='Glob pattern for PO files (repeatable)')
po_input_parser.add_argument('--exclude', action='append', help='Glob pattern to exclude (repeatable)')

# Sort control — used by scan, import, export
sort_parser = argparse.ArgumentParser(add_help=False)
sort_parser.add_argument('--sort-by', choices=['msgid', 'source'], default='msgid', help='Sort order for output')

# Glossary — used by scan, import, lint
glossary_parser = argparse.ArgumentParser(add_help=False)
glossary_parser.add_argument('--glossary', help='Glossary YAML file')

# Context — used by scan, import
context_parser = argparse.ArgumentParser(add_help=False)
context_parser.add_argument('--context-rules', help='Context rules YAML file')
context_parser.add_argument('--preset', help='Context preset name')

# Master CSV — used by import, export
master_parser = argparse.ArgumentParser(add_help=False)
master_parser.add_argument('--master', required=True, help='Path to master CSV file (*-<lang>.csv)')

# Master CSV language — used by import, export
lang_parser = argparse.ArgumentParser(add_help=False)
lang_parser.add_argument('--lang', help='Override target language')
```

### Subcommand definitions

```python
# scan: po_input + sort + glossary + context + own flags
scan_parser = subparsers.add_parser('scan',
                                    parents=[po_input_parser, sort_parser, glossary_parser, context_parser])
scan_parser.add_argument('-o', '--output', ...)

# import: master + po_input + sort + glossary + context + lang
import_parser = subparsers.add_parser('import',
                                      parents=[master_parser, po_input_parser, sort_parser, glossary_parser, context_parser, lang_parser])

# export: master + po_input + sort + lang + own flags
export_parser = subparsers.add_parser('export',
                                      parents=[master_parser, po_input_parser, sort_parser, lang_parser])
export_parser.add_argument('--status', action='append', ...)
export_parser.add_argument('--dry-run', ...)
export_parser.add_argument('-v', '--verbose', ...)

# lint: po_input + glossary
lint_parser = subparsers.add_parser('lint',
                                    parents=[po_input_parser, glossary_parser])
```

Future flags added to any parent parser automatically appear on all subcommands that use it.

## Shared PO File Resolution

### Helper function

```python
def resolve_po_files(positional_files, include_patterns, exclude_patterns):
    """Collect PO files from positional args and --include, minus --exclude.

    1. Start with positional files (already shell-expanded)
    2. Expand each --include pattern via glob (recursive=True)
    3. Union and deduplicate by resolved path
    4. Remove files matching any --exclude pattern
    5. Return sorted list of paths
    6. Raise error if no files remain
    """
```

This replaces per-subcommand file resolution. Used by `scan`, `import`, `export`, `lint`.

### Error messages

```
# No files from any source
Error: No PO files specified. Use positional arguments or --include.

# --include matched nothing
Warning: Pattern 'src/**/fr/LC_MESSAGES/django.po' matched no files.

# All files excluded
Error: No PO files remain after applying --exclude patterns.
```

## Implementation

### Changes to existing modules

- `cli.py`:
    - Extract shared argument groups into parent parsers
    - Rewire all subcommand definitions to use parent parsers
    - Change `import` and `export`: `master_csv` positional → `--master` flag (required)
    - Change `import` and `export`: `po_files` positional from `nargs='+'` to `nargs='*'`
    - Add `resolve_po_files()` shared helper
    - Add validation: at least one PO file from any source

### No changes to

- `master.py` — master CSV logic unchanged
- `po_writer.py` — export logic unchanged
- `linter.py`, `formatter.py`, `context.py`, `parser.py`, `exporter.py`

## Test Suite

### Unit tests: `tests/test_cli.py` (updates)

**`--master` flag:**

- `import --master` accepted, required
- `export --master` accepted, required
- `import` without `--master` → error
- `export` without `--master` → error

**Flag availability:**

- `import --include` accepted
- `import --sort-by` accepted
- `export --include` accepted
- `export --sort-by` accepted
- `scan --include` still works (regression)
- `lint --include` still works (regression)

**PO file resolution:**

- Positional only → files collected
- `--include` only → files collected via glob expansion
- Both positional + `--include` → union, deduplicated
- `--exclude` removes matching files from result
- `--include` with `**` recursive pattern → correctly expanded
- No files from any source → error with helpful message
- `--include` pattern matching no files → warning, continue if other files exist
- All files excluded by `--exclude` → error

**Flag combinations on `import`:**

- `--master` + `--include` + `--exclude` + `--glossary` + `--preset` + `--sort-by` + `--context-rules`
- `--master` + positional PO files
- `--master` + positional + `--include` (combined)

**Flag combinations on `export`:**

- `--master` + `--include` + `--exclude` + `--status` + `--dry-run` + `--sort-by` + `-v`
- `--master` + positional PO files

### Integration tests

- `import --master --include "**/*.po"` finds PO files recursively
- `export --master --include "**/*.po"` finds PO files recursively
- `import --master` with positional + `--include` merges both sources
- `import --master` with `--exclude` removes matched files
- `export --master --include` + `--exclude` + `--dry-run` combined
- All existing `scan`, `import`, `export`, `lint` tests pass (updated for `--master` flag)

### Regression tests

- Parent parser refactor must not change behavior of any existing flag
- `scan` and `lint` positional PO file behavior unchanged

## Documentation

### Update README.md

- Update `import` usage: `--master` flag instead of positional
- Update `export` usage: `--master` flag instead of positional
- Add `--include`/`--sort-by` to `import` and `export` examples
- Add note about positional + `--include` coexistence
- Add note about `**` recursive glob patterns

### Update CHANGELOG.md

Add entries under `[0.5.1]` section:

- Changed: `import` and `export` use `--master` flag instead of positional argument
- Added: `--include` and `--sort-by` flags for `import` subcommand
- Added: `--include` and `--sort-by` flags for `export` subcommand
- Changed: CLI refactored to use shared parent parsers for common flags
- Added: Shared `resolve_po_files()` helper for PO file collection

## Version

- Feature work on `feature/cli-harmonization` branch
- Merge `--no-ff` to `develop`
- Bump patch version → `0.5.1`
- Tag: `git tag -a v0.5.1 -m "Harmonize CLI flags, revive --master flag for import/export"`

## Constraints

- No new dependencies
- Backward compatible for `scan` and `lint` — existing usage unchanged
- Breaking change for `import` and `export` — master CSV moves from positional to `--master` flag (acceptable: pre-1.0, sole user)
- Follow existing code style and patterns from Stages 1–5
- Run full test suite before considering complete — all existing tests must pass
- Parent parser refactor is structural — no behavioral changes to existing logic
