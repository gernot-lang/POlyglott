# POlyglott Stage 6: DeepL Integration

## Overview

Add a `translate` subcommand that uses the DeepL API to machine-translate entries in the master CSV. This stage connects the translation workflow: the master CSV (Stage 5 `import`) identifies what needs translating, the glossary (Stage 2) protects key terms, context (Stage 3) improves translation quality, and DeepL provides the translations.

## Scope — Stage 6 ONLY

**In scope:**

- `translate` subcommand operating on master CSV
- DeepL API integration (Free and Pro tiers)
- Glossary term protection via DeepL's glossary feature
- Context passing to DeepL for improved translations
- Format string placeholder protection (`%(name)s`, `{name}`)
- Status lifecycle integration: translated entries marked as `machine`
- Dry-run mode for cost estimation
- Rate limiting and error handling
- Comprehensive test suite
- Documentation updates

**Out of scope (future):**

- Alternative translation providers (Google Translate, etc.)
- Batch optimization / caching of repeated translations
- Interactive review workflow

## CLI Design

### Usage

```bash
# Translate all untranslated entries in master CSV
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY

# Translate with glossary term protection
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY --glossary .polyglott-glossary.yaml

# Dry run — show what would be translated, estimate API usage
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY --dry-run

# Translate only entries with specific statuses
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY --status empty --status rejected

# Use environment variable for API key
export DEEPL_AUTH_KEY=YOUR_DEEPL_KEY
polyglott translate polyglott-accepted-de.csv

# Force re-translate machine-translated entries
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY --status machine
```

### Arguments

```
polyglott translate [OPTIONS] MASTER_CSV

Arguments:
  MASTER_CSV                 Path to master CSV file (*-<lang>.csv)

Options:
  --auth-key KEY             DeepL API authentication key (or set DEEPL_AUTH_KEY env var)
  --glossary FILE            Glossary YAML for term protection
  --status STATUS            Which statuses to translate (repeatable, default: empty)
  --dry-run                  Show what would be translated without calling API
  --lang LANG                Override target language (instead of inferring from filename)
  --format-handling          How to handle format strings (default: xml-tags)
```

### Behavior

1. Load master CSV
2. Filter entries by status (default: only `empty`)
3. For each entry to translate:
    - Protect format string placeholders
    - Send to DeepL API with target language and optional context
    - Restore placeholders in response
    - Update msgstr in master CSV
    - Set status to `machine`
    - Set score to empty (machine translations are unscored)
4. Write updated master CSV
5. Print summary: entries translated, API characters used, entries skipped

### Target language

Inferred from master CSV filename suffix (`*-de.csv` → `DE`), same as Stage 5 `import`. Override with `--lang`.

Map POlyglott language codes to DeepL language codes where they differ (e.g., `en` → `EN-US` or `EN-GB`).

## DeepL API Integration

### API client

Use the `deepl` Python package (official DeepL SDK).

```python
import deepl

translator = deepl.Translator(auth_key)
result = translator.translate_text(text, target_lang="DE")
```

### Free vs Pro tiers

- Both use the same SDK, different API endpoints
- The `deepl` package auto-detects based on the auth key suffix
- Free tier: 500,000 characters/month
- Pro tier: pay per character

### Data privacy

- DeepL Free: texts may be used to improve the service
- DeepL Pro: texts are not stored after translation
- Document this clearly — users processing sensitive translations should use Pro

## Format String Protection

PO files contain Python format strings that must not be translated:

- `%(name)s`, `%(count)d` — Python percent format
- `{name}`, `{0}`, `{}` — Python brace format

### Strategy: XML tag wrapping

Before sending to DeepL, wrap format strings in XML tags that DeepL preserves:

```python
# Before: "Upload %(count)d files to %(folder)s"
# Wrapped: "Upload <x id='1'>%(count)d</x> files to <x id='2'>%(folder)s</x>"

# DeepL translates, preserving XML tags
# After: "<x id='1'>%(count)d</x> Dateien in <x id='2'>%(folder)s</x> hochladen"

# Unwrap: "%(count)d Dateien in %(folder)s hochladen"
```

Use `tag_handling="xml"` in the DeepL API call. The `<x>` tags with unique IDs ensure placeholders survive translation and can be reliably restored.

## Glossary Term Protection

When `--glossary` is provided:

1. Load glossary YAML (Stage 2 terms format)
2. Upload as DeepL glossary (or reuse existing if unchanged)
3. Pass glossary ID with translation requests

DeepL's glossary feature ensures terms are translated consistently according to the glossary, independent of context.

### DeepL glossary management

- Create glossary via API: `translator.create_glossary(name, source_lang, target_lang, entries)`
- Glossaries are stored on DeepL's servers
- Check if glossary already exists (by name) before creating
- Delete and recreate if glossary content has changed

## Context Integration

When the master CSV has context information (from Stage 3):

- Pass context as additional information to DeepL
- Use DeepL's `context` parameter: provides surrounding text that influences translation but isn't translated itself
- Example: context `form_label` tells DeepL to use concise, label-appropriate phrasing

The context column values from Stage 3 can be used to construct meaningful context hints for DeepL.

## Status Lifecycle

After translation:

- `empty` → `machine` (newly translated)
- `rejected` → `machine` (if explicitly included via `--status rejected`)
- `machine` → `machine` (if re-translating via `--status machine`)
- `accepted` → never touched (unless user explicitly includes via `--status accepted`)
- `review` → never touched by default
- `conflict` → never touched by default
- `stale` → never touched

Score is cleared (set to empty) for all machine-translated entries — machine translations are unscored until human review.

## Dry Run

`--dry-run` outputs:

```
Dry run — no API calls will be made.

Entries to translate: 47
  - empty: 42
  - rejected: 5

Estimated characters: 3,847
DeepL Free tier: 500,000 chars/month (0.8% of monthly limit)

Skipped:
  - accepted: 120
  - review: 15
  - machine: 8
  - stale: 3
  - conflict: 2
```

## Error Handling

- Invalid API key → clear error message
- Rate limit exceeded → retry with backoff, then fail gracefully
- Network errors → retry with backoff
- Individual translation failure → skip entry, log warning, continue
- Quota exceeded → stop, save progress, report how many were translated
- Malformed API response → skip entry, log warning

**Critical: always save progress.** If translation is interrupted (quota, network, error), write the master CSV with whatever translations succeeded. Never lose completed work.

## Implementation

### New module: `src/polyglott/translator.py`

- `translate_entries(entries, auth_key, target_lang, glossary, context) -> list[MasterEntry]`
- `protect_format_strings(text) -> tuple[str, list]` — wrap placeholders, return mapping
- `restore_format_strings(text, mapping) -> str` — unwrap placeholders
- `upload_glossary(translator, glossary, source_lang, target_lang) -> glossary_id`
- `estimate_characters(entries) -> int` — for dry run

### Changes to existing modules

- `cli.py` — add `translate` subcommand
- `master.py` — may need minor adjustments for loading/saving with new status values

### No changes to

- `linter.py`, `formatter.py`, `context.py`, `parser.py`, `exporter.py`

### New dependency

- `deepl` — official DeepL Python SDK

## Test Suite

### Unit tests: `tests/test_translator.py`

**Format string protection:**

- Python percent format: `%(name)s` wrapped and restored correctly
- Python brace format: `{name}` wrapped and restored correctly
- Mixed formats in same string
- String with no format strings → passes through unchanged
- Multiple identical placeholders handled correctly
- Nested braces handled correctly

**Status filtering:**

- Default: only `empty` entries selected
- Custom: `--status empty --status rejected` selects both
- `accepted` entries never selected by default
- Explicit `--status accepted` overrides protection

**Glossary integration:**

- Glossary loaded and formatted for DeepL API
- Empty glossary handled gracefully

**Dry run:**

- Character count estimation correct
- No API calls made
- Summary output correct

**Error handling:**

- Invalid API key → appropriate error
- Network timeout → retry behavior
- Partial failure → progress saved

### Integration tests

- `translate` updates master CSV with machine translations
- Status correctly set to `machine` after translation
- Score cleared for machine-translated entries
- `--dry-run` produces output without modifying master CSV
- `--glossary` flag accepted and passed to API
- Missing API key → error message suggesting env var
- Existing `scan`, `import`, `export`, `lint` tests still pass

### Mock strategy

Use mocking for DeepL API calls in tests. Do not make real API calls in the test suite. The `deepl` package can be mocked at the translator level.

## Documentation

### Update README.md

Add `translate` subcommand documentation: usage, API key setup, glossary integration, format string handling, dry run, data privacy notes.

### Update CHANGELOG.md

Add entries under `[0.6.0]` section.

## Version

- Feature work on `feature/deepl` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.6.0`
- Tag: `git tag -a v0.6.0 -m "Add DeepL integration for machine translation"`

## Constraints

- New dependency: `deepl` (official DeepL Python SDK)
- Backward compatible — all existing CLI usage unchanged
- Follow existing code style and patterns from Stages 1–5
- Run full test suite before considering complete — all existing tests must pass
- Never lose translation progress — always save on interruption
- Mock all API calls in tests — no real DeepL requests in test suite
