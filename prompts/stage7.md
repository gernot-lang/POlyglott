# POlyglott Stage 7: Candidate Column & Column Sovereignty

## Overview

Enhance the master CSV handling with two complementary features: a `candidate` column for non-destructive machine translation, and column sovereignty — POlyglott only touches its own reserved columns, preserving any user-added columns untouched.

These changes affect `translate`, `import`, and `export` subcommands. Together they make the master CSV a safer, more flexible workspace where machine suggestions coexist with human translations and users can extend the CSV with their own metadata.

**Prerequisite:** Stage 6 bug fix (v0.6.1) — XML-escape `&`, `<`, `>` in non-placeholder text before sending to DeepL. Stage 7 builds on the corrected v0.6.1 codebase.

## Scope — Stage 7 ONLY

**In scope:**

- `candidate` column in master CSV for non-destructive machine translation
- Smart routing: `translate` writes to `msgstr` when empty, `candidate` when `msgstr` has content
- Column sovereignty: POlyglott defines reserved columns, preserves all others
- `import` preserves user columns on merge
- `export` ignores non-POlyglott columns (exports only what PO format needs)
- `translate` respects column boundaries
- Comprehensive test suite
- Documentation updates

**Out of scope (future):**

- `accept` subcommand to copy candidate → msgstr (review workflow)
- Diff/comparison view between msgstr and candidate
- Column validation or schema enforcement for user columns
- Candidate history (multiple candidates from different providers)

## Design

### Feature 1: Candidate Column

#### Problem

Stage 6 `translate` overwrites `msgstr` directly. This is destructive for re-translation scenarios:

- Human-reviewed translation replaced by machine output
- No way to compare existing translation with fresh machine suggestion
- Re-translating `machine` status entries loses the previous attempt

#### Solution

Add a `candidate` column to the master CSV. The `translate` subcommand routes output based on whether `msgstr` already has content:

| `msgstr` state | `translate` writes to | Status set to | Rationale                               |
|----------------|-----------------------|---------------|-----------------------------------------|
| Empty          | `msgstr`              | `machine`     | No existing translation — fill directly |
| Has content    | `candidate`           | unchanged     | Preserve existing — offer comparison    |

This enables a review workflow: scan the candidate, compare with current msgstr, accept or discard.

#### Column definition

```
candidate  — Machine translation suggestion when msgstr already populated.
             Empty when msgstr was empty at translation time (result went to msgstr).
             Cleared when candidate is accepted into msgstr (future Stage).
```

#### Translation routing logic

```python
def route_translation(row, translated_text: str) -> dict:
    """Decide where to write the translation result."""
    msgstr = row.get('msgstr', '').strip()

    if not msgstr:
        # Empty msgstr — write directly, set status to machine
        return {
            'msgstr': translated_text,
            'status': 'machine',
            'score': '',
            'candidate': '',
        }
    else:
        # Existing msgstr — write to candidate, don't touch status
        return {
            'candidate': translated_text,
            # msgstr, status, score unchanged
        }
```

#### CLI integration

The `translate` subcommand gains awareness of the candidate column but requires no new flags — routing is automatic based on content.

Summary output updated:

```
Translation complete:
  Source language: EN
  Target language: es
  Entries translated: 69
    → msgstr (was empty): 54
    → candidate (msgstr existed): 15
  Passthrough entries: 1
  Errors: 0
  Master CSV updated: polyglott-files-es.csv
```

#### Interaction with `--status` flag

When `--status machine` is used for re-translation:

- These entries have `msgstr` populated (from prior machine translation)
- New translation goes to `candidate` (not overwriting the existing machine translation)
- User can compare old machine vs. new machine attempt

When `--status empty` (default):

- These entries have empty `msgstr`
- Translation goes directly to `msgstr`, status set to `machine`
- `candidate` column left empty

When `--status review`:

- These entries have `msgstr` populated (under review)
- New translation goes to `candidate`
- Status remains `review` — human review continues with fresh machine suggestion available

### Feature 2: Column Sovereignty

#### Problem

The master CSV is currently implicitly all-POlyglott. Users who add custom columns (e.g., `notes`, `reviewer`, `priority`, `client_approved`) risk having them stripped, reordered, or corrupted by `import`, `translate`, or `export`.

#### Solution

Define a fixed set of **reserved columns** that POlyglott reads and writes. Everything else is pass-through — preserved on read, written back unchanged, never modified.

#### Reserved columns

```python
POLYGLOTT_COLUMNS = [
    'msgid',  # Source string (Stage 5 import)
    'msgstr',  # Translation (Stage 5 import / Stage 6 translate)
    'status',  # Lifecycle status (all stages)
    'score',  # Translation quality score (future)
    'context',  # Context description (Stage 3)
    'context_sources',  # Context source references (Stage 3)
    'candidate',  # Machine translation candidate (Stage 7)  ← NEW
]
```

#### Rules

1. **POlyglott reads/writes only reserved columns** — all operations scope to `POLYGLOTT_COLUMNS`
2. **User columns preserved verbatim** — column name, position, content untouched
3. **Column order**: POlyglott columns first (in defined order), then user columns (in their original order)
4. **New reserved columns added gracefully** — if `candidate` column doesn't exist, create it (don't error)
5. **No reserved name collisions** — if a user column name matches a reserved name, it IS the reserved column (not a conflict)
6. **Empty reserved columns are valid** — POlyglott doesn't require all reserved columns to be present

#### Implementation: master CSV I/O

```python
import pandas as pd

POLYGLOTT_COLUMNS = [
    'msgid', 'msgstr', 'status', 'score',
    'context', 'context_sources', 'candidate',
]


def load_master(path: str) -> pd.DataFrame:
    """Load master CSV, ensuring reserved columns exist."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    # Add missing reserved columns (e.g., candidate on first Stage 7 run)
    for col in POLYGLOTT_COLUMNS:
        if col not in df.columns:
            df[col] = ''

    return df


def save_master(df: pd.DataFrame, path: str) -> None:
    """Save master CSV with POlyglott columns first, user columns after."""
    # Separate reserved and user columns
    reserved = [c for c in POLYGLOTT_COLUMNS if c in df.columns]
    user = [c for c in df.columns if c not in POLYGLOTT_COLUMNS]

    # Write with stable column order
    df[reserved + user].to_csv(path, index=False)
```

#### Impact on existing subcommands

**`import` (Stage 5):**

- Merges PO file entries into master CSV
- Touches only `msgid`, `msgstr`, `status` columns
- User columns preserved through the merge (left join on `msgid`)
- New entries from PO get empty user columns
- Removed entries: user's choice (currently kept with `stale` status)

**`translate` (Stage 6):**

- Routes to `msgstr` or `candidate` (Feature 1)
- Updates `status` and `score` per routing logic
- Never touches user columns

**`export` (Stage 5):**

- Exports only PO-relevant data (`msgid`, `msgstr`, and metadata)
- User columns and `candidate` are not exported to PO files
- No change needed — export already selects specific columns

**`lint` (Stage 2):**

- Validates `msgid`/`msgstr` pairs
- Unaffected by additional columns

**`scan` (Stage 4):**

- Scans source code for translatable strings
- Doesn't touch master CSV directly
- Unaffected

## CLI Changes

### No new subcommands

Both features are enhancements to existing behavior. No new CLI flags required.

### Updated `translate` summary

The summary output distinguishes direct writes from candidate writes:

```
Translation complete:
  Source language: EN
  Target language: de
  Entries translated: 69
    → msgstr (was empty): 54
    → candidate (msgstr existed): 15
  Passthrough entries: 1
  Errors: 0
  Master CSV updated: polyglott-files-de.csv
```

### Updated `--dry-run` output

```
Dry run — no API calls will be made.

Entries to translate: 69
  → will write to msgstr (currently empty): 54
  → will write to candidate (msgstr exists): 15

Estimated characters: 5,230
DeepL Free tier: 500,000 chars/month (1.0% of monthly limit)

Passthrough (no API cost): 1
  - punctuation-only: 1

Skipped (status not selected):
  - accepted: 120
  - review: 15
```

## Implementation

### Changes to existing modules

**`master.py`:**

- Add `POLYGLOTT_COLUMNS` constant
- Update `load_master()` to ensure reserved columns exist, preserve user columns
- Update `save_master()` to enforce column ordering (reserved first, then user)
- Add `candidate` to reserved column list

**`translate.py`:**

- Update `_translate_single_line()` (or equivalent) to return the translated text without writing it
- Add routing logic: check `msgstr` content, write to `msgstr` or `candidate`
- Update summary counters: track `msgstr_writes` vs `candidate_writes`
- Update dry-run output to show routing breakdown

**`cli.py`:**

- Update `translate` summary output format
- Update `--dry-run` output format

### No changes to

- `linter.py`, `formatter.py`, `context.py`, `parser.py`, `exporter.py`, `scanner.py`

### No new dependencies

Both features use only pandas (already a dependency) and Python stdlib.

## Test Suite

### Unit tests: candidate routing

**Empty msgstr → direct write:**

```python
def test_translate_empty_msgstr_writes_to_msgstr():
    """Empty msgstr: translation goes to msgstr, status=machine."""
    row = {'msgid': 'Save', 'msgstr': '', 'status': 'empty', 'candidate': ''}
    result = route_translation(row, 'Guardar')
    assert result['msgstr'] == 'Guardar'
    assert result['status'] == 'machine'
    assert result['candidate'] == ''
```

**Populated msgstr → candidate write:**

```python
def test_translate_existing_msgstr_writes_to_candidate():
    """Existing msgstr: translation goes to candidate, status unchanged."""
    row = {'msgid': 'Save', 'msgstr': 'Speichern', 'status': 'accepted', 'candidate': ''}
    result = route_translation(row, 'Guardar')
    assert result.get('msgstr') is None  # not in update dict
    assert result['candidate'] == 'Guardar'
```

**Re-translate machine status:**

```python
def test_retranslate_machine_goes_to_candidate():
    """Re-translating machine entry: new result goes to candidate."""
    row = {'msgid': 'Save', 'msgstr': 'Guardar', 'status': 'machine', 'candidate': ''}
    result = route_translation(row, 'Almacenar')
    assert result['candidate'] == 'Almacenar'
    # msgstr keeps 'Guardar', status keeps 'machine'
```

**Whitespace-only msgstr treated as empty:**

```python
def test_whitespace_msgstr_treated_as_empty():
    """Whitespace-only msgstr is treated as empty → direct write."""
    row = {'msgid': 'Save', 'msgstr': '  ', 'status': 'empty', 'candidate': ''}
    result = route_translation(row, 'Guardar')
    assert result['msgstr'] == 'Guardar'
    assert result['status'] == 'machine'
```

### Unit tests: column sovereignty

**Preserve user columns on load/save roundtrip:**

```python
def test_user_columns_preserved(tmp_path):
    """User-added columns survive load → save cycle."""
    csv = tmp_path / 'test.csv'
    csv.write_text('msgid,msgstr,status,notes,reviewer\n'
                   'Save,Guardar,accepted,needs review,Alice\n')
    df = load_master(str(csv))
    assert 'notes' in df.columns
    assert 'reviewer' in df.columns
    save_master(df, str(csv))
    df2 = pd.read_csv(str(csv), dtype=str, keep_default_na=False)
    assert df2.loc[0, 'notes'] == 'needs review'
    assert df2.loc[0, 'reviewer'] == 'Alice'
```

**Column order: reserved first, user after:**

```python
def test_column_order_on_save(tmp_path):
    """Reserved columns come first, user columns maintain relative order."""
    csv = tmp_path / 'test.csv'
    csv.write_text('priority,msgid,msgstr,status,reviewer\n'
                   '1,Save,Guardar,accepted,Alice\n')
    df = load_master(str(csv))
    save_master(df, str(csv))
    df2 = pd.read_csv(str(csv), dtype=str, keep_default_na=False)
    cols = list(df2.columns)
    # Reserved columns first
    assert cols.index('msgid') < cols.index('priority')
    assert cols.index('msgstr') < cols.index('priority')
    # User columns maintain relative order
    assert cols.index('priority') < cols.index('reviewer')
```

**Missing reserved columns added gracefully:**

```python
def test_missing_candidate_column_added(tmp_path):
    """Pre-Stage 7 CSV gets candidate column added on load."""
    csv = tmp_path / 'test.csv'
    csv.write_text('msgid,msgstr,status\nSave,Guardar,accepted\n')
    df = load_master(str(csv))
    assert 'candidate' in df.columns
    assert df.loc[0, 'candidate'] == ''
```

**Import preserves user columns:**

```python
def test_import_preserves_user_columns(tmp_path):
    """Importing new PO entries doesn't strip user columns."""
    # Setup: master CSV with user column
    # Import: new PO file adds entries
    # Verify: existing rows keep user column values
    # Verify: new rows have empty user columns
    ...
```

**Export ignores non-PO columns:**

```python
def test_export_ignores_candidate_and_user_columns(tmp_path):
    """Export to PO only includes msgid/msgstr, not candidate or user columns."""
    ...
```

**Translate doesn't touch user columns:**

```python
def test_translate_preserves_user_columns(tmp_path):
    """Translation run leaves user columns untouched."""
    csv = tmp_path / 'test.csv'
    csv.write_text('msgid,msgstr,status,candidate,notes\n'
                   'Save,,empty,,important\n')
    # Run translate (mocked DeepL)
    # Verify notes column unchanged
    ...
```

### Integration tests

- Full translate → save cycle with candidate routing and user columns
- Import new PO into CSV with user columns — existing data preserved
- Export from CSV with user columns — PO file clean
- Re-translate with `--status machine` — candidates populated, user columns untouched
- Dry-run shows correct routing breakdown
- Pre-Stage 7 CSV (no `candidate` column) works without errors
- Existing `scan`, `import`, `export`, `lint`, `translate` tests still pass

## Migration

### Backward compatibility

- CSVs without `candidate` column: added automatically on load (empty)
- CSVs without user columns: work exactly as before
- All existing CLI usage unchanged
- No breaking changes to any subcommand

### Forward compatibility

- New reserved columns can be added to `POLYGLOTT_COLUMNS` in future stages
- Same pattern: added on load if missing, empty default
- User columns unaffected by reserved column additions

## Documentation

### Update README.md

- Document `candidate` column purpose and behavior
- Document column sovereignty: reserved vs. user columns
- Update translate workflow description with routing logic
- Add example showing user columns surviving operations

### Update CHANGELOG.md

Add entries under `[0.7.0]` section:

- Added: `candidate` column for non-destructive machine translation
- Added: Column sovereignty — user-added columns preserved across all operations
- Changed: `translate` routes to `msgstr` (empty) or `candidate` (populated)
- Changed: Translate summary shows routing breakdown

## Version

- Feature work on `feature/candidate-column` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.7.0`
- Tag: `git tag -a v0.7.0 -m "Add candidate column and column sovereignty"`

## Constraints

- No new dependencies
- Backward compatible — pre-Stage 7 CSVs work without migration
- Follow existing code style and patterns from Stages 1–6
- Run full test suite before considering complete — all existing tests must pass
- Column sovereignty is enforced by `load_master` / `save_master` — all subcommands go through these functions
- Reserved column list is the single source of truth — defined once in `master.py`
- User column content is never read, validated, or modified by POlyglott
