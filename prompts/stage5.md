# POlyglott Stage 5: Import, Export, and CLI Refactor

## Overview

Refactor the CLI to properly separate concerns between inspecting PO files and managing the translation master CSV. Stage 4 added master CSV functionality to the `scan` subcommand via `--master`. Stage 5 extracts that into a dedicated `import` subcommand, restores `scan` to its Stage 3 behavior, and adds an `export` subcommand for writing accepted translations back to PO files.

This completes the master CSV workflow triangle:

- **`import`**: PO files → master CSV (pull translations into the registry)
- **`export`**: master CSV → PO files (push accepted translations back)
- **`scan`**: PO files → per-file CSV (inspect and export, no state management)

The master CSV remains the source of truth for translation decisions. PO files remain the source of truth for source strings.

## Scope — Stage 5 ONLY

**In scope:**

- `import` subcommand (extracted from Stage 4's `scan --master`)
- `export` subcommand (new — write master CSV translations back to PO files)
- Restore `scan` to Stage 3 behavior (remove `--master` flag)
- Flexible master CSV naming with language inference from `-<lang>.csv` suffix
- `--lang` override flag for master CSV language
- Full file paths in all console output (cross-cutting fix)
- Comprehensive test suite
- Documentation updates

**Out of scope (future stages):**

- DeepL integration (Stage 6)
- Cross-translation scoring
- Interactive review workflow

## CLI Refactor

### Before (Stage 4)

```bash
# Master CSV via scan
polyglott scan --master polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po

# Scan without master — per-file CSV export
polyglott scan locale/de/LC_MESSAGES/django.po -o translations.csv
```

### After (Stage 5)

```bash
# Import PO data into master CSV
polyglott import master-de.csv locale/de/LC_MESSAGES/*.po

# Export accepted translations back to PO files
polyglott export master-de.csv locale/de/LC_MESSAGES/*.po

# Scan — per-file CSV export (Stage 3 behavior, no --master)
polyglott scan locale/de/LC_MESSAGES/django.po -o translations.csv
```

## `import` Subcommand

### Usage

```bash
# Create or update master CSV from all German PO files
polyglott import master-de.csv locale/de/LC_MESSAGES/*.po

# With context rules
polyglott import master-de.csv --context-rules .polyglott-context.yaml locale/de/LC_MESSAGES/*.po

# With context preset and glossary (for auto-scoring)
polyglott import master-de.csv --preset django --glossary .polyglott-glossary.yaml locale/de/LC_MESSAGES/*.po

# Multiple paths / globs
polyglott import master-de.csv locale/de/LC_MESSAGES/django.po apps/*/locale/de/LC_MESSAGES/django.po

# Split by area — multiple master CSVs for the same language
polyglott import help-pages-de.csv apps/help/locale/de/LC_MESSAGES/*.po
polyglott import navigation-de.csv apps/nav/locale/de/LC_MESSAGES/*.po

# Explicit language override
polyglott import --lang de translations.csv locale/de/LC_MESSAGES/*.po
```

### Arguments

```
polyglott import [OPTIONS] MASTER_CSV PO_FILES...

Arguments:
  MASTER_CSV                 Path to master CSV file (*-<lang>.csv)
  PO_FILES                   One or more PO files or glob patterns

Options:
  --glossary FILE            Glossary YAML for auto-scoring
  --context-rules FILE       Context rules YAML for context inference
  --preset NAME              Context preset (e.g., django)
  --lang LANG                Override target language (instead of inferring from filename)
```

### Behavior

Identical to Stage 4's `scan --master`, with these changes:

- First positional argument is the master CSV path (was `--master PATH`)
- Remaining positional arguments are PO files (unchanged)
- No `-o` / `--output` flag (not applicable — master CSV path is the first positional)
- Language inferred from filename suffix (see naming section below)

All master CSV logic — initial creation, merge rules, deduplication, glossary auto-scoring, context integration — remains exactly as specified in Stage 4. The `master.py` module is unchanged.

### Language inference

Target language inferred from the `-<lang>.csv` suffix of the master CSV filename:

```
master-de.csv                → de
polyglott-accepted-de.csv    → de
help-pages-de.csv            → de
navigation-de.csv            → de
forms-de.csv                 → de
de.csv                       → de
myproject-en-us.csv          → en-us
```

Split on `-`, take the last segment before `.csv`, validate against known language codes.

If inference fails (e.g., `translations.csv`), require `--lang`:

```
Error: Cannot infer target language from 'translations.csv'.
Use a filename ending in '-<lang>.csv' (e.g., 'translations-de.csv')
or specify --lang explicitly.
```

Precedence: `--lang` flag always wins over filename inference.

## `export` Subcommand

### Usage

```bash
# Export accepted translations back to PO files
polyglott export master-de.csv locale/de/LC_MESSAGES/*.po

# Dry run — show what would change without modifying files
polyglott export master-de.csv --dry-run locale/de/LC_MESSAGES/*.po

# Export additional statuses beyond accepted
polyglott export master-de.csv --status accepted --status machine locale/de/LC_MESSAGES/*.po

# Verbose — per-entry detail
polyglott export master-de.csv -v locale/de/LC_MESSAGES/*.po

# Explicit language override
polyglott export --lang de translations.csv locale/de/LC_MESSAGES/*.po
```

### Arguments

```
polyglott export [OPTIONS] MASTER_CSV PO_FILES...

Arguments:
  MASTER_CSV                 Path to master CSV file (*-<lang>.csv)
  PO_FILES                   One or more PO files or glob patterns

Options:
  --status STATUS            Which statuses to export (repeatable, default: accepted)
  --dry-run                  Show what would change without modifying PO files
  --lang LANG                Override target language (instead of inferring from filename)
  -v, --verbose              Show per-entry detail
```

### Behavior

1. Load master CSV
2. Parse all input PO files
3. For each PO entry whose msgid exists in master CSV with qualifying status:
    - Update msgstr in the PO entry from master CSV
    - Handle fuzzy flag (see below)
4. Write modified PO files in place
5. Print summary

### Status filtering

Default: only `accepted` entries are exported.

With `--status`: export entries matching any of the specified statuses.

```bash
# Only accepted (default)
polyglott export master-de.csv locale/de/LC_MESSAGES/*.po

# Accepted + machine translations
polyglott export master-de.csv --status accepted --status machine locale/de/LC_MESSAGES/*.po
```

### Entries not in master

PO entries whose msgid does not exist in the master CSV are left untouched. Export only modifies entries that exist in both the master and the PO file.

### Overwrite behavior

When a PO entry already has a msgstr that differs from the master CSV, export overwrites it. The master CSV is the source of truth for translation decisions.

### Fuzzy flag handling

- **`accepted`** entries: clear the fuzzy flag (translation is human-approved)
- **`machine`** entries: set the fuzzy flag (translation needs human review)
- **`review`** entries: leave fuzzy flag unchanged

### Console output

**Default — summary per file:**

```
Updated 47 entries across 3 files (12 overwrites)
  locale/de/LC_MESSAGES/django.po: 30 writes, 5 overwrites
  apps/accounts/locale/de/LC_MESSAGES/django.po: 10 writes, 4 overwrites
  apps/billing/locale/de/LC_MESSAGES/django.po: 7 writes, 3 overwrites
```

**Verbose (`-v`) — per-entry detail:**

```
WRITE    locale/de/LC_MESSAGES/django.po: "Save" → "Speichern"
OVERWRITE locale/de/LC_MESSAGES/django.po: "Upload file" — "Datei hochladen" → "Datei uploaden"
SKIP     locale/de/LC_MESSAGES/django.po: "Delete" — not in master
WRITE    apps/accounts/locale/de/LC_MESSAGES/django.po: "Login" → "Anmelden"
...

Updated 47 entries across 3 files (12 overwrites)
  locale/de/LC_MESSAGES/django.po: 30 writes, 5 overwrites
  apps/accounts/locale/de/LC_MESSAGES/django.po: 10 writes, 4 overwrites
  apps/billing/locale/de/LC_MESSAGES/django.po: 7 writes, 3 overwrites
```

**Dry run (`--dry-run`) — shows plan without modifying files:**

```
Dry run — no files will be modified.

Would update 47 entries across 3 files (12 overwrites)
  locale/de/LC_MESSAGES/django.po: 30 writes, 5 overwrites
  apps/accounts/locale/de/LC_MESSAGES/django.po: 10 writes, 4 overwrites
  apps/billing/locale/de/LC_MESSAGES/django.po: 7 writes, 3 overwrites
```

Combine `--dry-run` with `-v` for full per-entry detail without modifying anything.

## `scan` Restoration

### Change

Remove the `--master` flag from `scan`. Restore `scan` to its Stage 3 behavior: parse a PO file, export to per-file CSV.

### What stays

Everything from Stage 3:

```bash
# Export PO to CSV
polyglott scan locale/de/LC_MESSAGES/django.po -o translations.csv

# With context
polyglott scan locale/de/LC_MESSAGES/django.po --preset django -o translations.csv

# With glossary
polyglott scan locale/de/LC_MESSAGES/django.po --glossary .polyglott-glossary.yaml -o translations.csv
```

### What goes

- `--master` flag removed from `scan`
- `scan` no longer accepts multiple PO files (single file input, as in Stage 3)
- No master CSV creation/merge logic in `scan`

### Migration note

Users of `scan --master` switch to `import`:

```bash
# Before (Stage 4)
polyglott scan --master polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po

# After (Stage 5)
polyglott import polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po
```

## Cross-Cutting: Full Paths in Output

All commands that reference PO files in console output must use the full path as provided by the user (or expanded from glob), never just the basename. This applies to `scan`, `import`, `export`, and `lint`.

```
# CORRECT
WRITE locale/de/LC_MESSAGES/django.po: "Save" → "Speichern"
Warning: locale/de/LC_MESSAGES/django.po: entry count low

# WRONG
WRITE django.po: "Save" → "Speichern"
Warning: django.po: entry count low
```

This is necessary because multiple PO files share the same basename (`django.po`) in a Django project.

## Implementation

### New module: `src/polyglott/po_writer.py`

- `export_to_po(master_entries, po_path, statuses, dry_run, verbose) -> ExportResult`
- `ExportResult` dataclass: `writes, overwrites, skips, details`

### Changes to existing modules

- `cli.py`:
    - Add `import` subcommand (moves master CSV logic from `scan`)
    - Add `export` subcommand
    - Remove `--master` flag from `scan`
    - Add `--lang` flag to `import` and `export`
    - Add `-v` / `--verbose` flag to `export`
    - Add `--dry-run` flag to `export`
    - Add `--status` flag to `export`
    - Ensure all commands use full paths in output
- `master.py`:
    - Update `infer_language()` to use flexible `-<lang>.csv` suffix matching
    - Add `--lang` override support
    - No changes to core master CSV logic (create, merge, deduplicate)

### No changes to

- `linter.py` — lint unaffected
- `formatter.py` — text formatter unaffected
- `context.py` — context engine used as-is
- `parser.py` — PO parser used as-is
- `exporter.py` — per-file CSV export used as-is

## Test Suite

### Unit tests: `tests/test_po_writer.py`

**Export basics:**

- Accepted entry written to PO file
- Entry not in master → left untouched
- Empty msgstr in master → PO entry not modified
- Overwrite: PO has different msgstr → updated from master

**Status filtering:**

- Default: only `accepted` exported
- `--status accepted --status machine` exports both
- `review` not exported by default
- Explicit `--status review` includes review entries

**Fuzzy flag handling:**

- `accepted` entry → fuzzy flag cleared
- `machine` entry → fuzzy flag set
- `review` entry → fuzzy flag unchanged
- Entry not in master → fuzzy flag unchanged

**Dry run:**

- No PO files modified
- Summary output correct
- Verbose output correct

**Console output:**

- Full file paths used (not basenames)
- Summary counts correct
- Verbose per-entry lines correct
- Overwrite vs write correctly classified

### Unit tests: `tests/test_master.py` (updates)

**Language inference:**

- `master-de.csv` → `de`
- `polyglott-accepted-de.csv` → `de`
- `help-pages-de.csv` → `de`
- `de.csv` → `de`
- `myproject-en-us.csv` → `en-us`
- `translations.csv` → error
- `--lang de` with `translations.csv` → `de`
- `--lang` overrides filename inference

### Integration tests

**`import` subcommand:**

- `import` creates new master CSV
- `import` updates existing master CSV
- `import` with `--context-rules` adds context
- `import` with `--glossary` adds auto-scores
- `import` with no PO files → error
- `import` with non-inferrable filename and no `--lang` → error
- `import` with `--lang` override → correct language

**`export` subcommand:**

- `export` writes accepted translations to PO files
- `export` with `--status machine` includes machine translations
- `export` overwrites existing PO msgstr from master
- `export` leaves entries not in master untouched
- `export --dry-run` produces output without modifying PO files
- `export -v` shows per-entry detail
- `export --dry-run -v` combines both
- `export` clears fuzzy for accepted, sets fuzzy for machine

**`scan` restoration:**

- `scan` works as in Stage 3 (per-file CSV export)
- `scan --master` → error (flag removed)
- `scan` does not accept multiple PO files

**Backward compatibility:**

- All existing `scan` tests pass (Stage 3 behavior)
- All existing `lint` tests pass
- All existing `import`-related tests pass (migrated from `scan --master` tests)

**Round-trip:**

- `import` → manually set `accepted` in CSV → `export` → PO file updated correctly
- `import` → `translate` (Stage 6) → `export --status machine` → PO files get machine translations with fuzzy flag

### Test fixtures

- Master CSV with mixed statuses (accepted, machine, review, empty)
- PO file with existing translations (for overwrite testing)
- PO file with fuzzy entries (for flag handling)
- Multiple PO files sharing basename `django.po` (for path output testing)
- Reuse existing master CSV fixtures from Stage 4

## Documentation

### Update README.md

- Add `import` subcommand documentation
- Add `export` subcommand documentation
- Update `scan` documentation (remove `--master` references)
- Add migration note for `scan --master` → `import`
- Add workflow example: `import` → review in CSV → `export`
- Document flexible master CSV naming

### Update CHANGELOG.md

Add entries under `[0.5.0]` section:

- Added: `import` subcommand for master CSV management
- Added: `export` subcommand for writing translations back to PO files
- Added: Flexible master CSV naming (`*-<lang>.csv`)
- Added: `--lang` flag for explicit language override
- Changed: `scan` restored to Stage 3 behavior (per-file CSV export only)
- Removed: `--master` flag from `scan` subcommand
- Fixed: All commands now use full file paths in console output

## Version

- Feature work on `feature/import-export` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.5.0`
- Tag: `git tag -a v0.5.0 -m "Add import/export subcommands, restore scan to Stage 3 behavior"`

## Constraints

- No new dependencies (polib already available from Stage 1)
- Backward compatible — existing `scan` and `lint` usage unchanged
- Follow existing code style and patterns from Stages 1–4
- Run full test suite before considering complete — all existing tests must pass
- PO files written by `export` must be valid PO files that pass `msgfmt --check`
- Export modifies PO files in place — VCS is the safety net
