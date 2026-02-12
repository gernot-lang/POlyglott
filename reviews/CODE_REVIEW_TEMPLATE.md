# Code Review Report Template

**Project:** POlyglott  
**Version:** [version under review]  
**Reviewer:** Claude Code  
**Date:** [date]  
**Scope:** [what was reviewed and why]

---

## Summary

| Severity   | Count |
|------------|-------|
| Critical   | 0     |
| Major      | 0     |
| Minor      | 0     |
| Suggestion | 0     |

### Severity Definitions

- **Critical** — Bugs causing incorrect output, data loss, or security issues. Must fix before next release.
- **Major** — Incorrect behavior, missing error handling, test coverage gaps, misleading output. Should fix soon.
- **Minor** — Inconsistencies, naming issues, dead code, style violations, documentation gaps. Fix when convenient.
- **Suggestion** — Refactoring ideas, performance improvements, future-proofing. Optional, for discussion.

---

## Findings

### [SEVERITY-NNN] Short title describing the issue

- **File:** `src/polyglott/module.py`, line NN, `function_name()`
- **Category:** Bug | Test Gap | Error Handling | Style | Maintainability | Performance | Security | Documentation
- **Description:** Clear explanation of what is wrong and why it matters.
- **Evidence:**

```python
# Current code (problematic)
def example():
    ...
```

- **Impact:** What goes wrong for the user or developer.
- **Recommendation:**

```python
# Proposed fix
def example():
    ...
```

---

## Checklist

The following areas were reviewed:

- [ ] **CLI consistency** — All subcommands handle errors, missing args, and edge cases the same way
- [ ] **Flag completeness** — `--help` output matches stage spec for all subcommands
- [ ] **Master CSV logic** — Merge rules, status transitions, deduplication, encoding, quoting, BOM handling
- [ ] **Export logic** — Write/overwrite/skip counting, fuzzy flag handling, multiline msgid/msgstr
- [ ] **PO file resolution** — Glob expansion, `--include`/`--exclude` interaction, symlinks, permissions
- [ ] **Import/module hygiene** — No circular imports, no unused imports, no dead code
- [ ] **Test coverage** — All code paths exercised, edge cases covered, no hardcoded versions
- [ ] **Error messages** — Helpful, consistent, include file paths where relevant
- [ ] **Known issues** — Items listed in CLAUDE.md Known Issues section addressed

---

## Action Items

| ID        | Severity | Description         | Fix now? | Branch            |
|-----------|----------|---------------------|----------|-------------------|
| MAJOR-001 | Major    | [short description] | Yes      | `fix/description` |
| MINOR-001 | Minor    | [short description] | Stage 6  | —                 |

### Fix Priority

- **Fix now:** Create `fix/` branch, follow bugfix workflow in CLAUDE.md (TDD, both branches, patch bump)
- **Stage 6:** Bundle with next feature release
- **Deferred:** Track for future consideration, no immediate action

---

## Files Reviewed

| File                         | Lines | Notes                |
|------------------------------|-------|----------------------|
| `src/polyglott/cli.py`       | NNN   | [any relevant notes] |
| `src/polyglott/master.py`    | NNN   |                      |
| `src/polyglott/po_writer.py` | NNN   |                      |
| `src/polyglott/parser.py`    | NNN   |                      |
| `src/polyglott/exporter.py`  | NNN   |                      |
| `src/polyglott/linter.py`    | NNN   |                      |
| `src/polyglott/formatter.py` | NNN   |                      |
| `src/polyglott/context.py`   | NNN   |                      |
| `tests/test_cli.py`          | NNN   |                      |
| `tests/test_*.py`            | NNN   |                      |

---

## Reviewer Notes

[Any overall observations about code quality, architecture, patterns, or recommendations
that don't fit into individual findings. For example: "Codebase is well-structured,
consistent naming conventions, good test coverage overall. Main gap is error path testing."]
