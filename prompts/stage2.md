# POlyglott Stage 2: Lint Subcommand with Glossary

## Overview

Add a `lint` subcommand that checks PO files against configurable quality rules and reports violations. Includes glossary support for enforcing consistent terminology across translations.

## Scope — Stage 2 ONLY

**In scope:**

- `lint` subcommand with built-in quality checks
- Glossary YAML file for term consistency enforcement
- CSV and text output formats for lint results
- Severity levels and filtering
- Exit codes for CI/CD integration
- Comprehensive test suite
- Documentation updates

**Out of scope (future stages):**

- Context inference (Stage 3)
- Master CSV workflow (Stage 4)
- DeepL integration (Stage 5)
- CSV → PO import (future)

## Architecture

`lint` builds on top of `scan`. Both share the same pipeline: file discovery, PO parsing, entry collection. The difference is that `lint` runs checks against each entry and extends the CSV output with evaluation columns. Do not duplicate the shared pipeline — reuse existing `discover_files()`, `parse_po_file()`, and CSV export logic from Stage 1.

Before implementing, review the Stage 1 codebase to understand the existing structure.

## CLI Design

### Usage

```bash
# Basic lint — single file, built-in checks only, CSV to stdout
polyglott lint locale/de/LC_MESSAGES/django.po

# Multi-file with glob
polyglott lint --include "locale/**/*.po" -o lint-results.csv

# With glossary for term consistency
polyglott lint --include "locale/**/*.po" --glossary glossary.yaml -o lint-results.csv

# With exclude patterns
polyglott lint --include "**/*.po" --exclude "**/test/**" --glossary glossary.yaml -o lint-results.csv

# Terminal-friendly text output
polyglott lint --include "locale/**/*.po" --format text

# Filter by severity
polyglott lint --include "locale/**/*.po" --severity warning -o issues.csv

# Run specific checks only
polyglott lint --include "locale/**/*.po" --check format_mismatch --check fuzzy

# Exclude specific checks
polyglott lint --include "locale/**/*.po" --no-check obsolete
```

### Arguments

```
polyglott lint [OPTIONS] [FILE]

Arguments:
  FILE                       Single .po file to lint (optional if --include used)

Options:
  -o, --output FILE          Output file (default: stdout)
  --include PATTERN          Glob pattern(s) for .po files (repeatable)
  --exclude PATTERN          Glob pattern(s) to exclude (repeatable)
  --glossary FILE            Path to glossary YAML file
  --format [csv|text]        Output format (default: csv)
  --severity [error|warning|info]  Minimum severity to report (default: info)
  --check NAME               Run only specific check(s) (repeatable)
  --no-check NAME            Skip specific check(s) (repeatable)
```

### Exit Codes

- `0` — no errors or warnings (info-only is OK)
- `1` — errors found
- `2` — warnings found (no errors)

This enables CI integration: `polyglott lint --include "**/*.po" --glossary glossary.yaml || exit 1`

## Built-in Checks

These checks always run (no glossary required):

| Check             | Severity | Description                                         |
|-------------------|----------|-----------------------------------------------------|
| `untranslated`    | info     | `msgstr` is empty                                   |
| `fuzzy`           | warning  | Entry flagged `#, fuzzy`                            |
| `format_mismatch` | error    | Format placeholders in `msgid` don't match `msgstr` |
| `obsolete`        | info     | Entry marked obsolete (`#~`)                        |

### Format mismatch details

Detect both Python format styles:

- `%(name)s`, `%(count)d`, `%(total).1f` — Python percent format
- `{0}`, `{name}`, `{}` — Python brace format

Check both directions: placeholders missing from `msgstr` AND extra placeholders in `msgstr` not present in `msgid`.

## Glossary Check

Requires `--glossary` flag:

| Check           | Severity | Description                                         |
|-----------------|----------|-----------------------------------------------------|
| `term_mismatch` | warning  | `msgstr` uses wrong translation for a glossary term |

### Glossary file format

The glossary is a YAML file defining canonical translations for key terms:

```yaml
language: de

terms:
  pipeline: Pipeline
  node: Knoten
  edge: Kante
  link: Verbindung
  namespace: Namensraum
  owner: Eigentümer
  file: Datei
  folder: Ordner
```

### Term matching rules

- Match whole words only — "file" should not match "profile"
- Case-insensitive on the English side (msgid)
- If `msgid` contains a glossary term and `msgstr` does not contain the canonical translation, flag as `term_mismatch`
- Use word boundary awareness to avoid false positives

### Glossary validation

Validate the YAML on load. Fail fast with a clear error message on:

- Missing file
- Malformed YAML
- Missing `terms` section
- Empty terms

This adds a `pyyaml` dependency.

## Output Formats

### CSV (default)

The standard `scan` columns, extended with three evaluation columns:

| Column     | Description                                   |
|------------|-----------------------------------------------|
| `severity` | `error`, `warning`, or `info`                 |
| `check`    | Check name (e.g., `format_mismatch`, `fuzzy`) |
| `message`  | Human-readable description of the issue       |

**Only entries with issues are included.** Clean entries are omitted — this is the key difference from `scan`.

An entry can appear multiple times if it has multiple issues (e.g., both `fuzzy` and `term_mismatch`), resulting in multiple CSV rows.

### Text (`--format text`)

Terminal-friendly format grouped by file:

```
locale/de/LC_MESSAGES/django.po:
  ERROR   line 42    format_mismatch    msgid has %(file)s but msgstr is missing it
  WARNING line 15    term_mismatch      "link" should be "Verbindung", found "Verknüpfung"
  WARNING line 23    fuzzy              needs review
  INFO    line 156   untranslated       empty msgstr

Summary: 1 error, 2 warnings, 1 info — 4 issues in 1 file
```

## Implementation

### New modules

- `src/polyglott/linter.py` — check registry and check implementations
- `src/polyglott/formatter.py` — text output formatting

### Check architecture

Keep checks modular. Each check is a function that receives a parsed entry (and optionally the glossary) and returns zero or more violations. Use a decorator-based registry so new checks can be added easily:

```python
@register_check("format_mismatch", severity="error")
def check_format_mismatch(entry):
    # Extract placeholders, compare, return violations
    ...
```

### Changes to existing modules

- `cli.py` — add `lint` subcommand with all arguments
- `exporter.py` — accept optional lint columns, extend CSV output

### No changes to

- `parser.py` — PO parser used as-is

## Test Suite

### Test fixtures

Add to `tests/fixtures/`:

- PO file with format string issues (missing placeholders, extra placeholders)
- PO file with term consistency issues
- Glossary YAML file for testing

Reuse existing fixtures from Stage 1 where appropriate.

### Unit tests

**Built-in checks (each in isolation):**

- `untranslated`: empty msgstr detected
- `fuzzy`: fuzzy flag detected
- `format_mismatch`: missing placeholder detected, extra placeholder detected, matching placeholders pass
- `obsolete`: obsolete entry detected
- Clean entry produces no violations

**Glossary:**

- Load valid glossary YAML
- Error on missing file
- Error on malformed YAML
- Error on missing `terms` section
- `term_mismatch`: wrong translation detected
- `term_mismatch`: whole word boundary (no false positives)
- `term_mismatch`: case-insensitive English matching

**Output:**

- CSV has correct columns (scan columns + severity, check, message)
- Multiple violations per entry produce multiple rows
- Clean entries excluded from output
- Text format produces correct structure
- Severity filtering works
- `--check` and `--no-check` filtering works

**Exit codes:**

- 0 when no errors or warnings
- 1 when errors found
- 2 when warnings but no errors

### Integration tests

- `polyglott lint <file>` produces CSV output
- `polyglott lint <file> --format text` produces text output
- `polyglott lint <file> --glossary <file>` runs term checks
- `polyglott lint --include "**/*.po"` expands globs
- `polyglott lint --severity error` filters output
- Existing `scan` tests still pass (no regressions)

## Documentation

### Update README.md

Add `lint` subcommand to CLI reference. Add glossary file format documentation. Update roadmap to show Stage 2 complete.

### Update CHANGELOG.md

Add entries under `[0.2.0]` section.

## Version

- Feature work on `feature/lint` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.2.0`
- Tag: `git tag -a v0.2.0 -m "Add lint subcommand with glossary support"`

## Constraints

- New dependency: `pyyaml` (for glossary YAML parsing)
- Backward compatible — all existing `scan` CLI usage works identically
- Follow existing code style and patterns from Stage 1
- Run full test suite before considering complete — all existing tests must pass
