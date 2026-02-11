# POlyglott Stage 3: Context Inference from Source References

## Overview

Add context inference to POlyglott. PO files contain `#:` source reference comments that indicate where each translatable string originates. In structured frameworks like Django, these paths carry strong signal about what kind of UI element the string belongs to (form label, navigation item, log message, prose, etc.).

POlyglott should read a user-provided YAML rules file that maps path patterns to context labels, match each entry's `#:` references against those rules, and add `context` and `context_sources` columns to `scan` and `lint` CSV output.

## Scope — Stage 3 ONLY

**In scope:**

- `.polyglott-context.yaml` rules file parser
- Pattern matching engine for `#:` source references
- `context` and `context_sources` columns in `scan` CSV output
- `context` and `context_sources` columns in `lint` CSV output
- `--context-rules PATH` CLI flag for both `scan` and `lint`
- `--preset django` convenience flag with built-in Django path conventions
- Ambiguity handling when a single msgid has references matching different contexts
- Comprehensive test suite
- Documentation updates

**Out of scope (future stages):**

- Context-aware glossary rules (Stage 2 glossary unchanged)
- Context-aware lint checks (lint behaves identically regardless of context)
- Master CSV workflow (Stage 4)
- DeepL integration (Stage 5)

## Rules File Format

The rules file is `.polyglott-context.yaml`. Format:

```yaml
rules:
  - pattern: "tables.py"
    context: column_header

  - pattern: "forms.py"
    context: form_label

  - pattern: "forms/vertex_types/"
    context: form_label

  - pattern: "models.py"
    context: field_label

  - pattern: "views.py"
    context: message

  - pattern: "management/commands/"
    context: log_message

  - pattern: "sidebar.html"
    context: navigation

  - pattern: "navbar.html"
    context: navigation

  - pattern: "about.html"
    context: prose
```

Rules are simple substring matches against the file path portion of each `#:` reference (the part before the colon and line number). Rules are evaluated in order; first match wins for each individual reference.

Context labels are arbitrary strings — POlyglott does not validate them. The user chooses labels meaningful to their workflow.

## Django Preset

`--preset django` loads a built-in rules set:

```yaml
rules:
  - pattern: "tables.py"
    context: column_header
  - pattern: "forms.py"
    context: form_label
  - pattern: "forms/"
    context: form_label
  - pattern: "models.py"
    context: field_label
  - pattern: "serializers.py"
    context: field_label
  - pattern: "views.py"
    context: message
  - pattern: "management/commands/"
    context: log_message
  - pattern: "admin.py"
    context: admin
  - pattern: "sidebar"
    context: navigation
  - pattern: "navbar"
    context: navigation
  - pattern: "templates/"
    context: template
```

`--context-rules` and `--preset` are mutually exclusive. If both provided, exit with error.

## Matching Logic

### Per-reference matching

Each `#:` comment contains one or more `filepath:lineno` references. For each reference, extract the filepath (strip the `:lineno` suffix) and test it against the rules in order. First matching rule assigns the context for that reference.

### Aggregation across references

A single msgid may have multiple `#:` references resolving to different contexts:

1. **Unanimous** — all references resolve to the same context → assign that context
2. **Majority** — one context appears more than others → assign the majority context
3. **Tie** — no clear majority → assign `ambiguous`
4. **No match** — no references match any rule → empty string
5. **No references** — entry has no `#:` comments → empty string

### context_sources column

Shows the raw mapping for transparency. Format: semicolon-separated `filepath=context` pairs. Only populated when multiple distinct contexts exist (ambiguity). When all references agree, `context_sources` is empty.

## CLI Integration

### scan subcommand

```bash
# With explicit rules file
polyglott scan locale/de/LC_MESSAGES/django.po --context-rules .polyglott-context.yaml -o output.csv

# With Django preset
polyglott scan locale/de/LC_MESSAGES/django.po --preset django -o output.csv

# Without context (existing behavior unchanged)
polyglott scan locale/de/LC_MESSAGES/django.po -o output.csv
```

When context is active: CSV gains `context` and `context_sources` columns (after `references`).

When context is not active: these columns are omitted entirely. Existing behavior unchanged.

### lint subcommand

Same flags: `--context-rules PATH` and `--preset django`. Context columns added to lint CSV. Lint checks themselves are not affected by context — they run identically regardless.

### Flag validation

- `--context-rules` and `--preset` mutually exclusive → error if both provided
- Nonexistent rules file → error
- Invalid YAML → error with message
- Unrecognized preset name → error listing available presets

## Implementation

### New module: `src/polyglott/context.py`

- `load_context_rules(path: str) -> list[dict]` — parse YAML rules file
- `load_preset(name: str) -> list[dict]` — return built-in preset rules
- `PRESETS = {'django': [...]}` — built-in presets dict
- `match_context(references: list[str], rules: list[dict]) -> tuple[str, str]` — returns `(context, context_sources)`
- Validation functions for the rules file format

### Changes to existing modules

- `cli.py` — add `--context-rules` and `--preset` to both `scan` and `lint`
- `exporter.py` — accept optional context data, add columns to CSV output

### No changes to

- `linter.py` — lint checks unaffected
- `formatter.py` — text formatter unaffected (context only in CSV)
- `parser.py` — PO parser used as-is (verify `#:` references accessible via polib)

## Test Suite

### Unit tests: `tests/test_context.py`

**Rules loading:**

- Load valid YAML rules file
- Error on missing file
- Error on malformed YAML
- Error on YAML without `rules` key
- Error on rules with missing `pattern` or `context`
- Load Django preset

**Single-reference matching:**

- Reference matches first rule
- Reference matches second rule (first doesn't match)
- No rule matches → empty context
- Rule order matters (first match wins)
- Line number stripped correctly from reference

**Multi-reference matching (same context):**

- All references match same context → that context, empty context_sources

**Multi-reference matching (mixed contexts):**

- Clear majority → majority context, populated context_sources
- Tie → `ambiguous`, populated context_sources
- Mix of matched and unmatched → unmatched ignored for majority calculation

**Edge cases:**

- Entry with no references → empty context
- Entry with single reference → straightforward
- Empty rules list → all contexts empty

### Integration tests

- `scan` with `--context-rules` → CSV has context columns
- `scan` with `--preset django` → CSV has context columns
- `scan` without context flags → CSV has NO context columns (backward compatible)
- `--context-rules` and `--preset` together → error
- `lint` with `--preset django` → CSV has context columns alongside lint columns
- `lint` text output → context does NOT appear (text format unchanged)
- All existing Stage 1 and Stage 2 tests pass

### Test fixtures

Create:

- Test PO file with entries having varied `#:` references (single, multiple same, multiple different, none)
- Test rules YAML file matching the test PO entries
- Invalid rules YAML files for error tests

## Documentation

### Update README.md

Add context inference section: what it does, CLI flags, rules file format, Django preset, examples.

### Update CHANGELOG.md

Add entries under `[0.3.0]` section.

## Version

- Feature work on `feature/context-inference` branch
- Merge `--no-ff` to `develop`
- Bump minor version → `0.3.0`
- Tag: `git tag -a v0.3.0 -m "Add context inference from source references"`

## Constraints

- No new dependencies (pyyaml already present from Stage 2)
- Backward compatible — all existing CLI usage works identically without context flags
- Follow existing code style and patterns from Stages 1–2
- Run full test suite before considering complete — all existing tests must pass

## Development Notes

- Use venv tools: `.venv/bin/pytest`, `.venv/bin/bump-my-version`
- All 102+ existing tests must continue to pass (regression check)
- Create test fixtures in `tests/fixtures/` with descriptive names
- Follow the git workflow in CLAUDE.md (feature branch → develop → main → tag)
- Update both README.md and CHANGELOG.md before completing the stage
- Version bumping: `.venv/bin/bump-my-version bump minor` on develop branch
