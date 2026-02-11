# POlyglott Stage 4: Translation Master CSV

## Overview

Add a project-wide translation master CSV to POlyglott. Currently, `scan` exports individual PO files to CSV. Stage 4 introduces `--master` mode: scan multiple PO files, deduplicate by msgid, and produce a single master CSV per target language that tracks translation status and quality scores.

The master CSV becomes the central translation registry — the single place where translation state is tracked, reviewed, and managed. PO files remain the source of truth for source strings; the master CSV is the source of truth for translation decisions.

## Scope — Stage 4 ONLY

**In scope:**

- `--master PATH` flag for the `scan` subcommand
- Multiple PO file input (glob patterns and positional arguments)
- Deduplication by msgid across all input files
- Per-language master CSV with status and score columns
- Merge behavior: updating an existing master preserves human decisions
- Conflict detection when PO files diverge from accepted translations
- Glossary-based auto-scoring (score 10 for exact glossary term matches)
- Integration with Stage 3 context engine
- Comprehensive test suite
- Documentation updates

**Out of scope (future stages):**

- DeepL integration (Stage 5)
- Writing master CSV back to PO files (future `import` command)
- Cross-translation scoring
- DeepL glossary upload/management

## Master CSV Schema

### Filename convention

`polyglott-accepted-<lang>.csv` — one file per target language.

Examples: `polyglott-accepted-de.csv`, `polyglott-accepted-es.csv`

### Columns

| Column            | Description                                       |
|-------------------|---------------------------------------------------|
| `msgid`           | English source string (unique key)                |
| `msgstr`          | Translation in target language                    |
| `status`          | Translation lifecycle state                       |
| `score`           | Quality confidence, 1–10                          |
| `context`         | Inferred context from Stage 3 (if rules provided) |
| `context_sources` | Disambiguation detail (if ambiguity exists)       |

The `context` and `context_sources` columns are always present (empty if no context flags provided). This keeps the schema consistent.

### Status values

| Status     | Meaning                               | Set by                     |
|------------|---------------------------------------|----------------------------|
| `empty`    | No translation exists                 | `scan --master` (initial)  |
| `machine`  | Machine-translated, not reviewed      | Future `translate` command |
| `review`   | Has translation, needs human review   | `scan --master` (from PO)  |
| `accepted` | Human-approved translation            | Human (manual edit in CSV) |
| `rejected` | Explicitly marked as wrong            | Human (manual edit in CSV) |
| `stale`    | msgid no longer in any PO file        | `scan --master` (rescan)   |
| `conflict` | PO file diverges from accepted master | `scan --master` (rescan)   |

### Score values

| Score   | Meaning                    | Set by                     |
|---------|----------------------------|----------------------------|
| 10      | Exact glossary term match  | `scan --master` (auto)     |
| 1–9     | Reserved for future stages | Future `translate` command |
| (empty) | Not yet scored             | Default                    |

Score 10 is assigned automatically when msgid exactly matches a glossary term key AND msgstr exactly matches the glossary's translation.

## CLI Integration

### scan subcommand — master mode

```bash
# Create or update master CSV from all German PO files
polyglott scan --master polyglott-accepted-de.csv locale/de/LC_MESSAGES/*.po

# With context rules
polyglott scan --master polyglott-accepted-de.csv --context-rules .polyglott-context.yaml locale/de/LC_MESSAGES/*.po

# With context preset and glossary (for auto-scoring)
polyglott scan --master polyglott-accepted-de.csv --preset django --glossary .polyglott-glossary.yaml locale/de/LC_MESSAGES/*.po

# Multiple paths / globs
polyglott scan --master polyglott-accepted-de.csv locale/de/LC_MESSAGES/django.po apps/*/locale/de/LC_MESSAGES/django.po
```

### Behavior

When `--master` is provided:

- All input PO files are parsed and their entries collected
- Entries are deduplicated by msgid (same msgid across files = one row)
- If an existing master CSV exists at the path, it is loaded and merged (see merge rules)
- If no existing master CSV exists, a fresh one is created
- Output written to the `--master` path

When `--master` is NOT provided:

- Existing `scan` behavior completely unchanged

### Flag interactions

- `--master` and `-o` / `--output` are mutually exclusive → error if both provided
- `--master` works with `--context-rules`, `--preset`, and `--glossary`
- `--master` requires at least one PO file argument
- Target language inferred from filename: `polyglott-accepted-de.csv` → `de`. If filename doesn't match `polyglott-accepted-<lang>.csv`, exit with error.

## Initial Scan (No Existing Master)

When the master CSV does not yet exist:

1. Parse all input PO files
2. Collect all entries, deduplicate by msgid
3. For each unique msgid:
    - `msgstr`: take from PO entry. If multiple files have same msgid with different msgstr, take most common (majority wins). If tied, take first encountered.
    - `status`: `review` if msgstr non-empty, `empty` if msgstr empty
    - `score`: `10` if msgid+msgstr exactly match a glossary term (requires `--glossary`), empty otherwise
    - `context` / `context_sources`: populated if `--context-rules` or `--preset` provided
4. Write master CSV sorted alphabetically by msgid

## Rescan Merge Rules (Existing Master)

When the master CSV already exists, `scan --master` merges new PO data with existing decisions:

### Per-entry rules by status

| Existing status | PO has msgid? | PO msgstr matches?    | Action                                            |
|-----------------|---------------|-----------------------|---------------------------------------------------|
| `accepted`      | Yes           | Yes (matches master)  | No change                                         |
| `accepted`      | Yes           | No (different msgstr) | Status → `conflict`                               |
| `accepted`      | No            | —                     | Status → `stale`                                  |
| `rejected`      | Yes           | —                     | No change                                         |
| `rejected`      | No            | —                     | Status → `stale`                                  |
| `review`        | Yes           | —                     | Update msgstr from PO                             |
| `review`        | No            | —                     | Status → `stale`                                  |
| `machine`       | Yes           | —                     | Update msgstr from PO                             |
| `machine`       | No            | —                     | Status → `stale`                                  |
| `empty`         | Yes           | —                     | Populate msgstr if now non-empty, set `review`    |
| `empty`         | No            | —                     | Status → `stale`                                  |
| `conflict`      | Yes           | —                     | No change (requires manual resolution)            |
| `conflict`      | No            | —                     | Status → `stale`                                  |
| `stale`         | Yes           | —                     | Status → `review`, update msgstr                  |
| `stale`         | No            | —                     | No change                                         |
| (new msgid)     | Yes           | —                     | Add as `review` or `empty` per initial scan rules |

### Score preservation

- Rescan never modifies existing scores
- Score 10 (glossary match) only assigned on initial population or when status transitions from `empty` to `review`
- Human-assigned scores preserved across rescans

### Context update

- Context is always refreshed on rescan (derived from current PO references, not a human decision)
- Even `accepted` entries get updated context

## Glossary Auto-Scoring

When `--glossary` is provided with `--master`:

1. Load the glossary YAML (Stage 2 terms format)
2. For each entry being initially populated or transitioning from `empty`:
    - If msgid exactly matches a glossary term key AND msgstr exactly matches the term's translation → score = 10
3. Existing scores are never overwritten by auto-scoring

### Glossary format reference (Stage 2, terms only)

```yaml
language: de

terms:
  pipeline: Pipeline
  node: Knoten
  file: Datei
  folder: Ordner
```

## CSV Format Details

### Column order

`msgid, msgstr, status, score, context, context_sources`

### Encoding

UTF-8 with BOM (for Excel compatibility). Use `csv` module with proper quoting.

### Quoting

`csv.QUOTE_ALL` — all fields quoted. Prevents issues with translations containing commas or special characters.

### Sorting

Rows sorted alphabetically by msgid. Ensures stable diffs in version control.

## Implementation

### New module: `src/polyglott/master.py`

- `MasterEntry` dataclass: `msgid, msgstr, status, score, context, context_sources`
- `load_master(path: str) -> list[MasterEntry]` — load existing master CSV
- `save_master(entries: list[MasterEntry], path: str)` — write master CSV
- `create_master(po_entries, glossary, context_rules) -> list[MasterEntry]` — initial creation
- `merge_master(existing: list[MasterEntry], po_entries, glossary, context_rules) -> list[MasterEntry]` — rescan merge
- `deduplicate_entries(po_entries) -> dict` — group by msgid, resolve conflicts

### Changes to existing modules

- `cli.py` — add `--master` argument to `scan`, handle flag interactions and validation
- `exporter.py` — may need minor adjustments for master CSV format (or master.py handles its own export)

### No changes to

- `linter.py` — lint unaffected
- `formatter.py` — text formatter unaffected
- `context.py` — context engine used as-is
- `parser.py` — PO parser used as-is

## Multiple PO File Handling

### Entry collection

When multiple PO files are provided:

1. Parse each PO file with polib
2. For each entry, record: msgid, msgstr, source references, source PO file path
3. Group by msgid across all files

### Reference aggregation for context

When the same msgid appears in multiple PO files, their `#:` references are combined for context inference. More references = more signal for the context engine.

### Glob pattern handling

Accept standard glob patterns. Use Python's `glob.glob()` or `pathlib.Path.glob()`. If a pattern matches no files, print warning but continue. If no input files remain, exit with error.

## Test Suite

### Unit tests: `tests/test_master.py`

**Initial creation:**

- Single PO file → master with correct columns
- Multiple PO files → deduplicated by msgid
- Empty msgstr → status `empty`
- Non-empty msgstr → status `review`
- Glossary match → score 10
- Glossary partial match (msgid matches, msgstr doesn't) → no score
- No glossary → no scores
- Context populated when rules provided
- Context empty when no rules
- Master sorted alphabetically by msgid

**Deduplication:**

- Same msgid, same msgstr across files → one row
- Same msgid, different msgstr → majority wins, status `review`
- Same msgid, one empty and one non-empty → non-empty wins

**Merge — status transitions:**

Test each row of the merge rules table:

- `accepted` + matching PO → no change
- `accepted` + divergent PO → `conflict`
- `accepted` + missing from PO → `stale`
- `rejected` + present → no change
- `rejected` + missing → `stale`
- `review` + changed msgstr → updated
- `review` + missing → `stale`
- `machine` + changed msgstr → updated
- `machine` + missing → `stale`
- `empty` + now has msgstr → populated, `review`
- `empty` + still empty → no change
- `empty` + missing → `stale`
- `conflict` + present → no change
- `conflict` + missing → `stale`
- `stale` + reappears → `review`, msgstr updated
- New msgid → added as `empty` or `review`

**Score preservation:**

- Existing score survives rescan
- Glossary auto-score only on initial population
- Manual scores never overwritten

**Context refresh:**

- Context updated on rescan even for `accepted` entries
- References from all current PO files used

### Integration tests

- `scan --master` creates new master CSV
- `scan --master` updates existing master CSV
- `scan --master` with `--context-rules` adds context
- `scan --master` with `--glossary` adds auto-scores
- `scan --master` with `-o` → error
- `scan --master` with no PO files → error
- `scan --master` with invalid filename → error
- `scan` without `--master` → existing behavior unchanged
- Round-trip: create → modify status manually → rescan → verify preservation
- Round-trip: create → change PO file → rescan → verify conflict detection
- All existing tests pass

### Test fixtures

- Multiple PO files with overlapping msgids
- PO files with glossary-matching translations
- PO file with entries removed (stale detection)
- PO file with changed msgstr (conflict detection)
- Test glossary YAML for auto-scoring
- Reuse existing context test fixtures from Stage 3

## Documentation

### Update README.md

Add master CSV section: what it does, CLI usage, schema, merge behavior, workflow examples.

### Update CHANGELOG.md

Add entries under `[0.4.0]` section.

## Version

- Feature work on `feature/master-csv` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.4.0`
- Tag: `git tag -a v0.4.0 -m "Add translation master CSV with merge workflow"`

## Constraints

- No new dependencies (csv, glob, pathlib, dataclasses are all stdlib)
- Backward compatible — all existing `scan`, `lint` usage unchanged without `--master`
- Follow existing code style and patterns from Stages 1–3
- Run full test suite before considering complete — all existing tests must pass
- Master CSV must be valid, well-formed CSV that opens correctly in Excel, LibreOffice, and any CSV reader
