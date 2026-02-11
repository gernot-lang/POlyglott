# POlyglott

A tool for parsing gettext PO files and exporting them to CSV for translation workflow management.

## Features

- **PO File Parsing**: Extract all metadata from gettext PO files using polib
- **CSV Export**: Convert PO entries to CSV format with pandas
- **Quality Linting**: Check translations for common issues (untranslated, fuzzy, format mismatches)
- **Glossary Support**: Enforce translation consistency with YAML glossary files
- **Multi-file Support**: Process multiple PO files with glob patterns
- **Unicode Support**: Full support for international characters, emoji, and multi-byte scripts
- **Flexible Sorting**: Sort output by any field (msgid, msgstr, fuzzy status, etc.)
- **Statistics**: View translation progress (total, untranslated, fuzzy, plurals)
- **Command-line Interface**: Easy-to-use CLI with intuitive options

## Installation

### From Source

```bash
git clone <repository-url>
cd polyglott
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Requirements

- Python 3.10 or higher
- polib >= 1.2.0
- pandas >= 2.0.0
- pyyaml >= 6.0

## Usage

### Scan Command

Scan a single PO file and output to stdout:

```bash
polyglott scan messages.po
```

Save output to a CSV file:

```bash
polyglott scan messages.po -o output.csv
```

#### Multi-file Processing

Process multiple PO files using glob patterns:

```bash
polyglott scan --include "locales/**/*.po" -o translations.csv
```

Exclude specific files:

```bash
polyglott scan --include "**/*.po" --exclude "tests/**/*.po" -o output.csv
```

#### Sorting

Sort output by field:

```bash
polyglott scan messages.po --sort-by msgid -o sorted.csv
```

Available sort fields: `msgid`, `msgstr`, `source_file`, `fuzzy`

### Lint Command

Check translation quality with built-in validators:

```bash
polyglott lint messages.po
```

#### Text Output

Human-readable text format for terminal:

```bash
polyglott lint messages.po --format text
```

#### Glossary Checking

Enforce term consistency with a glossary file:

```bash
polyglott lint messages.po --glossary glossary.yaml
```

**Glossary Format (YAML):**

```yaml
language: de
terms:
  file: Datei
  folder: Ordner
  pipeline: Pipeline
```

#### Built-in Checks

- **untranslated** (error): Entry has no translation
- **fuzzy** (warning): Entry is marked as fuzzy
- **format_mismatch** (error): Format placeholders don't match (e.g., `%(name)s`, `{count}`)
- **term_mismatch** (warning): Translation doesn't use glossary term
- **obsolete** (info): Entry is marked as obsolete

#### Filtering

Filter by severity level:

```bash
polyglott lint messages.po --severity error  # Only errors
```

Include/exclude specific checks:

```bash
polyglott lint messages.po --check untranslated --check fuzzy
polyglott lint messages.po --no-check obsolete
```

#### Exit Codes

- `0`: No issues found
- `1`: Errors found
- `2`: Warnings found (no errors)

Perfect for CI/CD pipelines:

```bash
polyglott lint locales/de.po || exit 1
```

### Context Inference

POlyglott can infer the UI context for each translatable string based on its source code location. This helps translators understand where the text appears (form labels, navigation, log messages, etc.).

#### Using Context Rules

Create a `.polyglott-context.yaml` file to map file path patterns to context labels:

```yaml
rules:
  - pattern: "tables.py"
    context: column_header

  - pattern: "forms.py"
    context: form_label

  - pattern: "models.py"
    context: field_label

  - pattern: "views.py"
    context: message

  - pattern: "management/commands/"
    context: log_message

  - pattern: "sidebar.html"
    context: navigation
```

Use with scan or lint:

```bash
polyglott scan messages.po --context-rules .polyglott-context.yaml -o output.csv
polyglott lint messages.po --context-rules .polyglott-context.yaml -o issues.csv
```

#### Django Preset

For Django projects, use the built-in preset:

```bash
polyglott scan messages.po --preset django -o output.csv
```

The Django preset includes common patterns:

- `tables.py` → column_header
- `forms.py`, `forms/` → form_label
- `models.py`, `serializers.py` → field_label
- `views.py` → message
- `management/commands/` → log_message
- `admin.py` → admin
- `sidebar`, `navbar` → navigation
- `templates/` → template

#### Context Columns

When context inference is active, CSV output includes:

- **context**: The inferred context label (or `ambiguous` for conflicting contexts, empty for no match)
- **context_sources**: Semicolon-separated `filepath=context` pairs (only populated when ambiguous)

**Ambiguity Handling:**

- If all source references agree on a context → use that context
- If one context has a clear majority → use the majority context
- If there's a tie → mark as `ambiguous` and populate `context_sources`
- If no references match any rule → leave empty

**Example:**

```bash
$ polyglott scan django.po --preset django -o output.csv
```

The CSV will include context columns showing where each string originates in your code.

#### Notes

- Context flags are optional — without them, output is identical to Stage 1/2
- `--context-rules` and `--preset` are mutually exclusive
- Context labels are arbitrary strings you define
- Rules use simple substring matching (first match wins)
- Context appears in CSV output only (not in lint text format)

### Master CSV

POlyglott can consolidate translations from multiple PO files into a **master CSV** that serves as the central translation registry. The master CSV deduplicates entries by msgid, tracks translation status, preserves human decisions, and detects conflicts when PO files diverge from accepted translations.

#### What is Master CSV?

The master CSV is a project-wide translation registry that:

- **Deduplicates by msgid**: Same msgid across multiple PO files → single master row
- **Tracks status lifecycle**: `empty` → `review` → `accepted`/`rejected` → `stale` → `conflict`
- **Preserves human decisions**: Accepted/rejected translations survive rescans
- **Auto-scores glossary matches**: Assigns quality score for exact glossary matches
- **Refreshes context**: Context is recomputed on every rescan to reflect current codebase
- **Detects conflicts**: Flags when PO files diverge from accepted translations

#### Creating a Master CSV

Use the `--master` flag instead of `-o/--output`:

```bash
polyglott scan messages.po --master polyglott-accepted-de.csv
```

**Filename format:** Must match `polyglott-accepted-<lang>.csv` pattern (e.g., `polyglott-accepted-de.csv`, `polyglott-accepted-fr.csv`)

#### Master CSV Schema

The master CSV has a fixed schema optimized for translation management:

| Column | Description |
|--------|-------------|
| `msgid` | Source text (deduplication key) |
| `msgstr` | Translation text |
| `status` | Translation status (see below) |
| `score` | Quality score (empty or "10" for glossary match) |
| `context` | Inferred UI context |
| `context_sources` | Disambiguation info (when ambiguous) |

#### Status Values

| Status | Meaning | Typical Workflow |
|--------|---------|------------------|
| `empty` | No translation yet | Initial scan of untranslated entries |
| `review` | Has translation, needs review | Default for translated entries; edit in CSV |
| `accepted` | Reviewed and approved | Mark as accepted after review |
| `rejected` | Rejected translation | Mark as rejected to skip |
| `conflict` | PO diverged from accepted | Resolve manually, then re-accept |
| `stale` | Removed from PO files | Entry no longer in codebase |
| `machine` | Machine-translated (future) | For auto-translated entries |

#### Merge Workflow

The master CSV merge preserves human decisions when rescanning:

```bash
# 1. Initial scan - creates master
polyglott scan django.po --master polyglott-accepted-de.csv

# 2. Review in CSV editor (Excel, LibreOffice, etc.)
#    - Check translations in 'review' status
#    - Change status to 'accepted' or 'rejected'
#    - Optionally edit msgstr or add custom scores

# 3. Rescan after code changes - updates master
polyglott scan django.po --master polyglott-accepted-de.csv

# Master CSV merge rules:
# - accepted + matching PO → no change
# - accepted + divergent PO → conflict (preserves your translation)
# - rejected + present → no change
# - review → updates msgstr from PO
# - empty + now has msgstr → review
# - missing from PO → stale
```

#### Multi-file Deduplication

When scanning multiple PO files, the master CSV deduplicates by msgid:

```bash
polyglott scan --include "locales/*/django.po" --master polyglott-accepted-de.csv
```

**Deduplication rules:**
- Same msgid across files → single master row
- References aggregated from all files (for context inference)
- Msgstr conflicts resolved by majority voting (most common wins)
- Non-empty msgstr beats empty

#### With Glossary Scoring

Combine with `--glossary` to auto-score exact matches:

```bash
polyglott scan django.po \
  --master polyglott-accepted-de.csv \
  --glossary glossary-de.yaml
```

Entries with exact glossary matches (case-insensitive) receive `score: 10`. Scores are preserved on rescan (human decisions).

#### With Context Rules

Combine with `--context-rules` or `--preset` to populate context columns:

```bash
polyglott scan django.po \
  --master polyglott-accepted-de.csv \
  --preset django
```

Context is refreshed on every rescan (derived data, not a human decision).

#### Conflict Detection

When accepted translations diverge from PO files:

```bash
# Initial: Password → "Passwort" (accepted)
polyglott scan de.po --master polyglott-accepted-de.csv
# (mark Password as accepted in CSV)

# Later: PO file changes Password → "Kennwort"
polyglott scan de.po --master polyglott-accepted-de.csv

# Master CSV:
# msgid: Password
# msgstr: Passwort (preserved)
# status: conflict (flags the divergence)
```

**Resolution workflow:**
1. Review the conflict
2. Either accept the new PO translation or keep your version
3. Manually update status back to `accepted`

#### Status Transitions

The merge workflow implements these status transitions:

- **accepted** + matching PO → stays `accepted`
- **accepted** + divergent PO → becomes `conflict`
- **accepted** + missing from PO → becomes `stale`
- **review** + present in PO → updates msgstr, stays `review`
- **review** + missing from PO → becomes `stale`
- **empty** + now has msgstr → becomes `review`, assigns score if glossary match
- **empty** + still empty → stays `empty`
- **empty** + missing from PO → becomes `stale`
- **conflict** + present → stays `conflict` (manual resolution required)
- **stale** + reappears in PO → becomes `review`, updates msgstr
- **new msgid** → added as `empty` or `review`

#### Notes

- `--master` and `-o/--output` are mutually exclusive
- Filename must match `polyglott-accepted-<lang>.csv` pattern
- CSV uses UTF-8 BOM, all fields quoted, sorted by msgid
- Score preservation: existing scores never overwritten (human decisions)
- Context refresh: always recomputed from current PO files
- Plurals and msgctxt: currently ignored in master CSV (v0.4.0 scope)

### Examples

**Scan single file with sorting:**

```bash
polyglott scan de.po --sort-by msgid -o german.csv
```

**Scan multiple languages:**

```bash
polyglott scan --include "locales/*/LC_MESSAGES/*.po" -o all_translations.csv
```

**Lint with glossary in CI:**

```bash
polyglott lint locales/de.po --glossary glossaries/de.yaml --severity warning
```

**Lint all files with text output:**

```bash
polyglott lint --include "**/*.po" --exclude "vendor/*.po" --format text
```

## Output Format

### Scan CSV Columns

- `msgid`: Original message string
- `msgstr`: Translated string
- `msgctxt`: Message context (optional)
- `extracted_comments`: Comments extracted from source code
- `translator_comments`: Translator-added comments
- `references`: Source code locations (file:line)
- `fuzzy`: Fuzzy translation flag (True/False)
- `obsolete`: Obsolete entry flag (True/False)
- `is_plural`: Plural form flag (True/False)
- `plural_index`: Plural form index (0, 1, 2, ...)

Multi-file mode adds `source_file` as the first column.

Context inference (with `--context-rules` or `--preset`) adds:

- `context`: Inferred UI context label
- `context_sources`: Disambiguation info (only when ambiguous)

### Lint CSV Columns

Lint mode includes all scan columns plus:

- `severity`: error, warning, or info
- `check`: Name of the check that failed
- `message`: Description of the issue

Context columns (`context`, `context_sources`) are also included when using `--context-rules` or `--preset`.

### Lint Text Format

```
format_issues.po:
-----------------
  ERROR   line 15    format_mismatch      Format placeholder mismatch (missing: %(value)s)
  ERROR   line 20    format_mismatch      Format placeholder mismatch (extra: %(extra)s)

------------------------------------------------------------
2 errors — 2 issues in 1 file
```

## Statistics

POlyglott displays statistics to stderr (keeping stdout clean for CSV output):

```
Statistics:
  Total entries: 245
  Untranslated: 42
  Fuzzy: 8
  Plurals: 15
  Files processed: 3
```

## Use Cases

- **Translation Management**: Export PO files to CSV for review in spreadsheet tools
- **Quality Assurance**: Lint translations for common issues before deployment
- **CI/CD Integration**: Enforce translation quality in automated pipelines
- **Glossary Enforcement**: Ensure consistent terminology across translations
- **Progress Tracking**: Monitor translation completion across multiple languages
- **Data Analysis**: Analyze translation patterns with pandas or Excel

## Development

### Running Tests

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/test_parser.py  # Specific module
```

### Project Structure

```
src/polyglott/
├── __init__.py      # Package init with __version__
├── __main__.py      # Support for python -m polyglott
├── cli.py           # CLI entry point (argparse)
├── parser.py        # PO file parsing (polib)
├── exporter.py      # CSV export (pandas)
├── linter.py        # Quality checks and glossary
├── formatter.py     # Text output formatting
├── context.py       # Context inference from source references
└── master.py        # Master CSV management and merge workflow
```

## Roadmap

POlyglott is under active development:

- **Stage 1 (v0.1.0)**: ✅ PO scanning and CSV export
- **Stage 2 (v0.2.0)**: ✅ Lint subcommand with glossary support
- **Stage 3 (v0.3.0)**: ✅ Context inference from source code references
- **Stage 4 (v0.4.0)**: ✅ Translation master CSV for multi-language management
- **Stage 5 (v0.5.0)**: DeepL integration for machine translation

See `prompts/` directory for detailed stage specifications.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE.md](LICENSE.md) for details.

## Acknowledgments

Built with:

- [polib](https://pypi.org/project/polib/) - PO file parsing
- [pandas](https://pandas.pydata.org/) - Data manipulation and CSV export
- [pyyaml](https://pyyaml.org/) - Glossary file parsing
- [pytest](https://pytest.org/) - Testing framework
