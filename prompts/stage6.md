# POlyglott Stage 6: DeepL Integration

## Overview

Add a `translate` subcommand that uses the DeepL API to machine-translate entries in the master CSV. This stage connects the translation workflow: the master CSV (Stage 5 `import`) identifies what needs translating, the glossary (Stage 2) protects key terms, context (Stage 3) improves translation quality, and DeepL provides the translations.

The implementation is informed by empirical spike testing (v1–v3) that validated placeholder protection strategies, glossary behavior, context effectiveness, and edge cases against 25 real Django admin translations across three DeepL API experiments.

## Scope — Stage 6 ONLY

**In scope:**

- `translate` subcommand operating on master CSV
- DeepL API integration (Free and Pro tiers)
- Format string placeholder protection via Strategy C (XML-wrapped + `ignore_tags`)
- Spacing normalization post-processor
- Pre-filter for passthrough strings
- Multiline string handling
- Glossary term protection via ephemeral DeepL glossaries
- Context passing to DeepL (critical for short strings)
- Translator backend protocol for future provider support
- Status lifecycle integration: translated entries marked as `machine`
- Dry-run mode for cost estimation
- Rate limiting and error handling
- Comprehensive test suite
- Documentation updates

**Out of scope (future):**

- Alternative translation providers (Google Translate, etc.) — adapter interface ready
- Batch optimization / caching of repeated translations
- Interactive review workflow

## CLI Design

### Usage

```bash
# Translate all untranslated entries in master CSV
polyglott translate polyglott-accepted-de.csv --auth-key YOUR_DEEPL_KEY

# Translate with glossary term protection
polyglott translate polyglott-accepted-de.csv --glossary glossary-de.yaml

# Dry run — show what would be translated, estimate API usage
polyglott translate polyglott-accepted-de.csv --dry-run

# Translate only entries with specific statuses
polyglott translate polyglott-accepted-de.csv --status empty --status rejected

# Use environment variable for API key
export DEEPL_AUTH_KEY=YOUR_DEEPL_KEY
polyglott translate polyglott-accepted-de.csv

# Force re-translate machine-translated entries
polyglott translate polyglott-accepted-de.csv --status machine
```

### Arguments

```
polyglott translate [OPTIONS] MASTER_CSV

Arguments:
  MASTER_CSV                 Path to master CSV file (*-<lang>.csv)

Options:
  --auth-key KEY             DeepL API authentication key (or set DEEPL_AUTH_KEY env var)
  --glossary FILE            Per-language glossary YAML for term protection
  --status STATUS            Which statuses to translate (repeatable, default: empty)
  --dry-run                  Show what would be translated without calling API
  --lang LANG                Override target language (instead of inferring from filename)
```

### Behavior

1. Load master CSV
2. Filter entries by status (default: only `empty`)
3. If `--glossary` provided, create ephemeral DeepL glossary
4. For each entry to translate:
   a. Pre-filter: skip passthrough strings (see Pre-Filter section)
   b. Pre-process: split multiline strings on `\n`, protect HTML entities
   c. Tokenize: wrap placeholders in `<x id="N">original</x>` tags
   d. Translate: call DeepL with `tag_handling="xml"`, `ignore_tags="x"`, optional `context`
   e. Restore: strip XML wrapper tags, restoring original placeholders
   f. Post-process: normalize spacing around placeholders, rejoin multilines
   g. Update msgstr in master CSV
   h. Set status to `machine`, clear score
5. If glossary was created, delete it
6. Write updated master CSV
7. Print summary: entries translated, API characters used, entries skipped

### Target language

Inferred from master CSV filename suffix (`*-de.csv` → `DE`), same as Stage 5 `import`. Override with `--lang`.

Map POlyglott language codes to DeepL language codes where they differ (e.g., `en` → `EN-US` or `EN-GB`).

## DeepL API Integration

### API client

Use the `deepl` Python package (official DeepL SDK).

```python
import deepl

translator = deepl.Translator(auth_key)
result = translator.translate_text(
    text,
    source_lang="EN",
    target_lang="DE",
    tag_handling="xml",
    ignore_tags="x",
)
```

### Required parameters for placeholder protection

Every translation call with placeholders MUST include:

- `tag_handling="xml"` — enables XML tag processing
- `ignore_tags="x"` — prevents DeepL from translating content inside `<x>` tags

Without `ignore_tags`, DeepL translates content inside tags: `%(error_code)d` becomes `%(Fehlercode)d`. This was the critical discovery from spike v1→v3.

### Free vs Pro tiers

- Both use the same SDK, different API endpoints
- The `deepl` package auto-detects based on the auth key suffix (`:fx` = Free)
- Free tier: 500,000 characters/month
- Pro tier: pay per character

### Data privacy

- DeepL Free: texts may be used to improve the service
- DeepL Pro: texts are not stored after translation
- Document this clearly — users processing sensitive translations should use Pro

## Format String Protection — Strategy C

### Background (spike results)

Three strategies were tested empirically against 25 Django admin translations:

| Strategy | Approach                          | Exact matches   | Spacing issues | Word order                       |
|----------|-----------------------------------|-----------------|----------------|----------------------------------|
| A (v1)   | XML-wrapped, no `ignore_tags`     | N/A — broken    | N/A            | N/A                              |
| B (v2)   | Opaque self-closing `<x id="N"/>` | 7/25 (28%)      | 7              | Wrong on every placeholder entry |
| C (v3)   | XML-wrapped + `ignore_tags="x"`   | **12/25 (48%)** | 5              | **Correct for most entries**     |

Strategy A failed completely — DeepL translated placeholder content inside tags (`%(error_code)d` → `%(Fehlercode)d`).

Strategy B preserved placeholders but produced wrong word order. DeepL sees self-closing tags as zero-width tokens and cannot reposition them for German SOV syntax: `"Add %(name)s"` → `"Hinzufügen %(name)s"` instead of `"%(name)s hinzufügen"`.

**Strategy C is the production path.** With `ignore_tags="x"`, DeepL preserves placeholder content verbatim AND treats the tag as having width/content, enabling correct word-order restructuring: `"Add %(name)s"` → `"%(name)s hinzufügen"` ✓.

Note: DeepL's own official mustache example uses Strategy B (opaque tokens without `ignore_tags`). Strategy C outperforms it because `ignore_tags` was added to the API after that example was written.

### Implementation

**Tokenization** — wrap format strings in XML tags before sending to DeepL:

```python
import re

PERCENT_FMT = re.compile(r"%(?:\([\w]+\))?[diouxXeEfFgGcrsab%]")
BRACE_FMT = re.compile(r"\{[\w]*(?::[^}]*)?\}")


def tokenize(text: str) -> tuple[str, list[str]]:
    """Wrap placeholders in <x id="N">original</x> for DeepL."""
    placeholders = []
    counter = 0

    def replace(match):
        nonlocal counter
        counter += 1
        placeholders.append(match.group(0))
        return f'<x id="{counter}">{match.group(0)}</x>'

    result = PERCENT_FMT.sub(replace, text)
    result = BRACE_FMT.sub(replace, result)
    return result, placeholders


def restore(text: str) -> str:
    """Remove XML wrapper tags, keeping content (which ignore_tags preserved)."""
    return re.sub(r'<x id="\d+">(.*?)</x>', r'\1', text)
```

**Example pipeline:**

```python
# Input
msgid = "Upload %(count)d files to %(folder)s"

# Tokenize
wrapped = 'Upload <x id="1">%(count)d</x> files to <x id="2">%(folder)s</x>'

# DeepL API call (with ignore_tags="x")
raw = '<x id="1">%(count)d</x> Dateien nach <x id="2">%(folder)s</x> hochladen'

# Restore
result = "%(count)d Dateien nach %(folder)s hochladen"
```

### Spacing normalization

Strategy C still exhibits occasional spacing collapse where DeepL removes spaces adjacent to tags. Spike v3 showed 5 spacing issues across 25 entries, e.g.:

- `Ausgewählte%(verbose_name_plural)s löschen` (missing space before placeholder)
- `{object}" hinzugefügt.` (missing space after closing quote following placeholder)

**Post-processor** — normalize spacing after placeholder restoration:

```python
def normalize_spacing(text: str, placeholders: list[str]) -> str:
    """Ensure single space around placeholders where needed."""
    for ph in placeholders:
        idx = text.find(ph)
        if idx < 0:
            continue
        end = idx + len(ph)
        # Ensure space before (unless at start or preceded by opening punct)
        if idx > 0 and text[idx - 1] not in (' ', '\n', '(', '„', '\u201e', '"'):
            text = text[:idx] + ' ' + text[idx:]
            end += 1
        # Ensure space after (unless at end or followed by closing punct)
        if end < len(text) and text[end] not in (' ', '.', ',', '!', '?', ')', '"', '\u201c', ':', ';', '\n'):
            text = text[:end] + ' ' + text[end:]
    # Collapse double spaces
    text = re.sub(r'  +', ' ', text)
    return text
```

This is a heuristic. Some false positives are possible (e.g., inserting a space before a period when a placeholder ends a sentence). The flag to `machine` status signals human review is expected.

## Pre-Filter

Some strings should bypass translation entirely. Spike v2 found:

- `"OK"` → `"In Ordnung."` — DeepL over-translates short tokens that should stay as-is
- Whitespace-only strings collapsed to single space
- Single characters and punctuation-only strings need no translation

### Passthrough rules

Skip DeepL and copy msgid directly to msgstr when:

1. String is whitespace-only or empty
2. String contains only punctuation/symbols (e.g., `"..."`, `"—"`, `"/"`)
3. String is in a configurable passthrough list (default: `["OK", "N/A"]`)
4. String consists entirely of format placeholders with no translatable text

Passthrough entries still get status `machine` — they are programmatically determined, not human-reviewed.

## Multiline String Handling

PO files contain multiline strings joined with `\n`. Spike v2 found that DeepL collapses newlines: `"Hello\nWorld"` → `"Hallo Welt"`.

**Strategy:** Split on `\n`, translate each line independently, rejoin:

```python
def translate_multiline(text: str, translate_fn) -> str:
    if '\n' not in text:
        return translate_fn(text)
    lines = text.split('\n')
    translated = [translate_fn(line) if line.strip() else line for line in lines]
    return '\n'.join(translated)
```

This preserves line structure. Each line gets its own API call, which costs slightly more characters but maintains formatting. Empty lines pass through without API calls.

## HTML Entity Handling

Spike v2 found HTML entities are catastrophically misinterpreted: `"&amp;"` → `"Und so weiter"` (DeepL reads `&amp;` as "and" and expands it to a phrase).

**Strategy:** Decode HTML entities before translation, re-encode after:

```python
import html


def protect_entities(text: str) -> tuple[str, bool]:
    """Decode HTML entities before DeepL. Returns (decoded, had_entities)."""
    decoded = html.unescape(text)
    return decoded, decoded != text


def restore_entities(text: str) -> str:
    """Re-encode the critical HTML entities."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
```

Only apply entity restoration when the original contained entities. Most PO strings don't.

## Glossary Term Protection

### Per-language YAML glossaries

Glossary files follow the existing Stage 2 format with a `language` key:

```yaml
# glossary-es.yaml
language: es
terms:
  pipeline: Pipeline
  hash: Hash
  namespace: Espacio de nombres
  node: Nodo
```

The `--glossary` flag accepts the per-language file matching the target language.

### Effectiveness

Spike v2 experiment 4 showed no measurable impact for common technical terms — DeepL already handled "Dashboard", "Pipeline", "Dateimanager" correctly without a glossary. However, glossaries are worth supporting for:

- Domain-specific terms that DeepL might mistranslate (e.g., "Vertex" → "Scheitelpunkt" when "Knoten" is wanted)
- Terms that should stay in English (like "Pipeline", "Hash") where DeepL might over-translate in some contexts
- Enforcing consistency across large translation batches

### Ephemeral glossary lifecycle

DeepL glossaries are API-managed objects stored on DeepL's servers. For a CLI tool, stateless ephemeral management is simplest:

```
1. Create glossary from YAML terms → glossary_id
2. Pass glossary_id with all translation calls
3. Delete glossary after translation run completes (or fails)
```

Always delete in a `finally` block. Never leave orphaned glossaries on DeepL's servers.

### API requirements

- `source_lang` is **required** when using glossaries (spike v2 found this)
- Glossary language pair must match translation direction exactly
- Create: `translator.create_glossary(name, source_lang, target_lang, entries_dict)`
- Delete: `translator.delete_glossary(glossary)`

## Context Integration

### Effectiveness (spike results)

Spike v2 experiment 3 found context impact is **significant for short strings, negligible for sentences**:

- `"Save"` — untranslated without context, `"Speichern"` with context `"Button label"`
- `"Cancel"` — `"Abbrechen"` (dialog context) vs `"Stornieren"` (order context)
- `"Run"` — `"Ausführen"` (execute context) vs `"Laufen"` (sports context)
- Longer strings (5+ words): context made no measurable difference

### Implementation

Pass the master CSV's context column value to DeepL's `context` parameter when available:

```python
kwargs = {
    "target_lang": target_lang,
    "source_lang": source_lang,
    "tag_handling": "xml",
    "ignore_tags": "x",
}
if context_value:
    kwargs["context"] = context_value
if glossary:
    kwargs["glossary"] = glossary

result = translator.translate_text(wrapped_text, **kwargs)
```

Context is advisory — it influences DeepL's word choice but is not translated itself. Don't skip entries that lack context; it only helps, never hurts.

## Translator Backend Protocol

Stage 6 implements DeepL only but defines an adapter interface for future providers. The tokenization strategy is API-specific (DeepL uses `ignore_tags`; Google Translate would need a different approach), so each backend owns its full translate-with-placeholders pipeline:

```python
from typing import Protocol


class TranslatorBackend(Protocol):
    def translate_entry(
            self,
            msgid: str,
            source_lang: str,
            target_lang: str,
            context: str | None = None,
            glossary_entries: dict[str, str] | None = None,
    ) -> str:
        """Translate a single PO entry, handling placeholder protection internally.

        Returns translated string with all original placeholders intact.
        """
        ...

    def estimate_characters(self, text: str) -> int:
        """Estimate API character cost for a string."""
        ...
```

The `translate` subcommand calls `translate_entry()` — it never knows about XML tags, `ignore_tags`, or any API-specific details. Each backend handles tokenization, API call, restoration, and spacing normalization internally.

Stage 6 ships `DeepLBackend` implementing this protocol. Future stages can add `GoogleBackend` etc. with a `--backend` CLI flag.

## Status Lifecycle

After translation:

- `empty` → `machine` (newly translated)
- `rejected` → `machine` (if explicitly included via `--status rejected`)
- `machine` → `machine` (if re-translating via `--status machine`)
- `accepted` → never touched (unless user explicitly includes via `--status accepted`)
- `review` → never touched by default
- `conflict` → never touched by default
- `stale` → never touched

Score is cleared (set to empty) for all machine-translated entries — machine translations are unscored until human review. Spike results (48% exact match rate for German) confirm that machine translations are first drafts, not publish-ready.

## Dry Run

`--dry-run` outputs:

```
Dry run — no API calls will be made.

Entries to translate: 47
  - empty: 42
  - rejected: 5

Estimated characters: 3,847
DeepL Free tier: 500,000 chars/month (0.8% of monthly limit)

Passthrough (no API cost): 3
  - whitespace/empty: 1
  - punctuation-only: 1
  - passthrough list: 1

Skipped (status not selected):
  - accepted: 120
  - review: 15
  - machine: 8
  - stale: 3
  - conflict: 2
```

Character estimation counts the wrapped XML form (what actually gets sent to the API), not the raw msgid.

## Error Handling

- Invalid API key → clear error message with hint about `DEEPL_AUTH_KEY` env var
- Rate limit exceeded → retry with exponential backoff (DeepL SDK handles this), then fail gracefully
- Network errors → retry with backoff
- Individual translation failure → skip entry, log warning, continue
- Quota exceeded → stop, save progress, report how many were translated
- Malformed API response → skip entry, log warning
- Glossary creation failure → warn and continue without glossary (graceful degradation)
- Glossary cleanup failure → warn but don't fail the run

**Critical: always save progress.** If translation is interrupted (quota, network, Ctrl+C), write the master CSV with whatever translations succeeded. Never lose completed work. Use `try/finally` to ensure the CSV write happens.

## Implementation

### New module: `src/polyglott/translate.py`

Core translation pipeline:

- `DeepLBackend` — implements `TranslatorBackend` protocol
- `DeepLBackend.translate_entry()` — full pipeline: pre-filter → tokenize → API call → restore → spacing fix
- `DeepLBackend.estimate_characters()` — for dry run
- `tokenize(text)` → `tuple[str, list[str]]` — wrap placeholders in `<x>` tags
- `restore(text)` → `str` — strip XML wrappers
- `normalize_spacing(text, placeholders)` → `str` — fix spacing collapse
- `is_passthrough(text)` → `bool` — pre-filter check
- `translate_multiline(text, translate_fn)` → `str` — split/translate/rejoin on `\n`

Glossary management:

- `create_ephemeral_glossary(translator, terms, source_lang, target_lang)` → glossary object
- `delete_glossary(translator, glossary)` — cleanup, never raises

### Changes to existing modules

- `cli.py` — add `translate` subcommand
- `master.py` — may need minor adjustments for loading/saving with new status values

### No changes to

- `linter.py`, `formatter.py`, `context.py`, `parser.py`, `exporter.py`

### New dependency

- `deepl` — official DeepL Python SDK (add to `pyproject.toml` as optional: `pip install polyglott[deepl]`)

Making `deepl` optional keeps the base package lightweight for users who don't need machine translation.

## Test Suite

### Unit tests: `tests/test_translate.py`

**Tokenization (Strategy C):**

- `%(name)s` → `<x id="1">%(name)s</x>` and back
- `{name}` → `<x id="1">{name}</x>` and back
- Mixed percent and brace formats in same string
- String with no placeholders → passes through unchanged
- Multiple placeholders get sequential IDs
- Restore strips XML wrappers cleanly

**Spacing normalization:**

- `"Ausgewählte%(name)s löschen"` → `"Ausgewählte %(name)s löschen"` (space inserted before)
- `"Geändert{fields}  für"` → `"Geändert {fields} für"` (space inserted, double collapsed)
- No false insertion before punctuation: `"%(count)d."` stays `"%(count)d."`
- Already-correct spacing unchanged

**Pre-filter:**

- `"OK"` → passthrough (returns msgid directly)
- `"..."` → passthrough
- `" "` → passthrough
- `"%(count)d files"` → not passthrough (has translatable text)
- `"%(name)s"` → passthrough (placeholder-only, nothing to translate)

**Multiline handling:**

- `"Hello\nWorld"` → split, translate each, rejoin with `\n`
- `"Line1\n\nLine3"` → empty line preserved without API call
- No `\n` in string → single translate call

**HTML entity handling:**

- `"&amp;"` decoded before translation, re-encoded after
- String without entities → no encode/decode overhead

**Status filtering:**

- Default: only `empty` entries selected
- Custom: `--status empty --status rejected` selects both
- `accepted` entries never selected by default
- Explicit `--status accepted` overrides protection

**Glossary management:**

- Glossary YAML loaded correctly
- Ephemeral create/delete lifecycle
- Missing glossary file → clear error
- Empty terms dict → skip glossary creation
- Glossary cleanup in `finally` block even on failure

**Dry run:**

- Character count estimation matches wrapped form
- No API calls made
- Passthrough entries excluded from character count
- Summary output correct

**Backend protocol:**

- `DeepLBackend` satisfies `TranslatorBackend` protocol
- `translate_entry()` returns string with placeholders intact
- `estimate_characters()` returns int

**Error handling:**

- Invalid API key → appropriate error
- Network timeout → retry behavior
- Partial failure → progress saved
- Glossary cleanup on failure

### Integration tests

- `translate` updates master CSV with machine translations
- Status correctly set to `machine` after translation
- Score cleared for machine-translated entries
- Passthrough entries get status `machine` with msgid copied to msgstr
- `--dry-run` produces output without modifying master CSV
- `--glossary` flag loads YAML and creates/deletes DeepL glossary
- Missing API key → error message suggesting env var
- Interrupted run → partial progress saved
- Existing `scan`, `import`, `export`, `lint` tests still pass

### Mock strategy

Use mocking for DeepL API calls in tests. Do not make real API calls in the test suite. Mock at the `deepl.Translator` level. Test the full pipeline (tokenize → mock API → restore → spacing fix) to verify end-to-end behavior.

For realistic mock responses, use patterns from spike v3 results (e.g., return German translations with known spacing issues to verify the post-processor catches them).

## Spike Evidence Summary

Three spikes (v1–v3) consumed 3,480 of 500,000 free-tier characters (0.7%) and validated:

| Finding                                                  | Spike  | Impact                                   |
|----------------------------------------------------------|--------|------------------------------------------|
| `ignore_tags="x"` prevents placeholder translation       | v1→v3  | **Critical** — chose Strategy C          |
| Strategy C: 48% exact match, correct word order          | v3     | Strategy selection                       |
| Strategy B: 28% exact match, broken word order           | v2, v3 | Rejected as primary strategy             |
| Spacing collapse requires post-processor                 | v2, v3 | Added normalize_spacing                  |
| Context critical for short strings only                  | v2     | Pass when available, don't require       |
| Glossary no impact for common terms                      | v2     | Support but don't depend on              |
| `source_lang` required for glossary API                  | v2     | Implementation detail                    |
| "OK" over-translated to "In Ordnung."                    | v2     | Added passthrough pre-filter             |
| Newlines collapsed by DeepL                              | v2     | Added multiline split/rejoin             |
| HTML entities misinterpreted                             | v2     | Added entity decode/re-encode            |
| DeepL v2 tag handling is account default (post Dec 2025) | v2     | No need for `tag_handling_version` param |

## Documentation

### Update README.md

Add `translate` subcommand documentation: usage, API key setup, glossary integration, dry run, data privacy notes. Document that machine translations are first drafts (48% exact match rate against professional human translations for German).

### Update CHANGELOG.md

Add entries under `[0.6.0]` section.

## Version

- Feature work on `feature/deepl` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.6.0`
- Tag: `git tag -a v0.6.0 -m "Add DeepL integration for machine translation"`

## Constraints

- New dependency: `deepl` (official DeepL Python SDK, optional via extras)
- Backward compatible — all existing CLI usage unchanged
- Follow existing code style and patterns from Stages 1–5
- Run full test suite before considering complete — all existing tests must pass
- Never lose translation progress — always save on interruption
- Mock all API calls in tests — no real DeepL requests in test suite
- Glossary lifecycle: always clean up ephemeral glossaries (create in setup, delete in finally)
