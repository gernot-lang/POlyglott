"""Linter for PO file quality checks."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml

from polyglott.parser import POEntryData


class Severity(Enum):
    """Violation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __lt__(self, other):
        """Compare severity levels (error > warning > info)."""
        order = {"error": 3, "warning": 2, "info": 1}
        return order[self.value] < order[other.value]


@dataclass
class Violation:
    """Represents a single linting violation."""

    entry: POEntryData
    severity: Severity
    check_name: str
    message: str


class Glossary:
    """Manages glossary terms for translation consistency checks."""

    def __init__(self, filepath: str):
        """Load glossary from YAML file.

        Args:
            filepath: Path to the YAML glossary file

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the glossary is invalid
        """
        self.filepath = Path(filepath)

        if not self.filepath.exists():
            raise FileNotFoundError(f"Glossary file not found: {filepath}")

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in glossary file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read glossary file: {e}")

        if not isinstance(data, dict):
            raise ValueError("Glossary must be a YAML dictionary")

        if 'terms' not in data:
            raise ValueError("Glossary must have a 'terms' section")

        if not data['terms']:
            raise ValueError("Glossary 'terms' section is empty")

        self.language = data.get('language', 'unknown')
        self.terms = data['terms']

        # Precompile regex patterns for performance
        self._patterns = {}
        for source_term, translation in self.terms.items():
            # Word boundary pattern for case-insensitive source matching
            pattern = re.compile(
                r'\b' + re.escape(source_term) + r'\b',
                re.IGNORECASE
            )
            self._patterns[source_term] = {
                'source_pattern': pattern,
                'translation': translation
            }

    def check_term(self, msgid: str, msgstr: str) -> Optional[str]:
        """Check if msgstr uses correct glossary terms.

        Args:
            msgid: Source text
            msgstr: Translation text

        Returns:
            Error message if mismatch found, None otherwise
        """
        if not msgstr:  # Skip untranslated entries
            return None

        for source_term, data in self._patterns.items():
            # Check if source term appears in msgid
            if data['source_pattern'].search(msgid):
                expected_translation = data['translation']

                # Check if translation uses the expected term (case-sensitive)
                translation_pattern = re.compile(
                    r'\b' + re.escape(expected_translation) + r'\b'
                )

                if not translation_pattern.search(msgstr):
                    return (
                        f"Expected glossary term '{expected_translation}' "
                        f"for '{source_term}' not found in translation"
                    )

        return None


class CheckRegistry:
    """Registry for linting checks with decorator-based registration."""

    def __init__(self):
        """Initialize the check registry."""
        self._checks: Dict[str, Callable] = {}

    def register(
            self,
            name: str,
            severity: Severity = Severity.ERROR
    ) -> Callable:
        """Decorator to register a check function.

        Args:
            name: Name of the check
            severity: Default severity level

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self._checks[name] = {
                'function': func,
                'severity': severity,
                'name': name
            }
            return func
        return decorator

    def get_check(self, name: str) -> Optional[Dict]:
        """Get a check by name.

        Args:
            name: Name of the check

        Returns:
            Check dictionary or None if not found
        """
        return self._checks.get(name)

    def get_all_checks(self) -> Dict[str, Dict]:
        """Get all registered checks.

        Returns:
            Dictionary of all checks
        """
        return self._checks.copy()

    def get_active_checks(
            self,
            include: Optional[List[str]] = None,
            exclude: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """Get active checks based on include/exclude filters.

        Args:
            include: List of check names to include (None = all)
            exclude: List of check names to exclude

        Returns:
            Dictionary of active checks
        """
        checks = self.get_all_checks()

        if include:
            checks = {name: check for name, check in checks.items() if name in include}

        if exclude:
            checks = {name: check for name, check in checks.items() if name not in exclude}

        return checks


# Global registry instance
registry = CheckRegistry()


@registry.register('untranslated', Severity.ERROR)
def check_untranslated(
        entry: POEntryData,
        glossary: Optional[Glossary] = None
) -> Optional[Violation]:
    """Check if entry is untranslated.

    Args:
        entry: PO entry to check
        glossary: Optional glossary (not used by this check)

    Returns:
        Violation if untranslated, None otherwise
    """
    if not entry.msgstr and not entry.obsolete:
        return Violation(
            entry=entry,
            severity=Severity.ERROR,
            check_name='untranslated',
            message='Entry is not translated'
        )
    return None


@registry.register('fuzzy', Severity.WARNING)
def check_fuzzy(
        entry: POEntryData,
        glossary: Optional[Glossary] = None
) -> Optional[Violation]:
    """Check if entry is marked as fuzzy.

    Args:
        entry: PO entry to check
        glossary: Optional glossary (not used by this check)

    Returns:
        Violation if fuzzy, None otherwise
    """
    if entry.fuzzy:
        return Violation(
            entry=entry,
            severity=Severity.WARNING,
            check_name='fuzzy',
            message='Entry is marked as fuzzy'
        )
    return None


@registry.register('obsolete', Severity.INFO)
def check_obsolete(
        entry: POEntryData,
        glossary: Optional[Glossary] = None
) -> Optional[Violation]:
    """Check if entry is obsolete.

    Args:
        entry: PO entry to check
        glossary: Optional glossary (not used by this check)

    Returns:
        Violation if obsolete, None otherwise
    """
    if entry.obsolete:
        return Violation(
            entry=entry,
            severity=Severity.INFO,
            check_name='obsolete',
            message='Entry is obsolete'
        )
    return None


@registry.register('format_mismatch', Severity.ERROR)
def check_format_mismatch(
        entry: POEntryData,
        glossary: Optional[Glossary] = None
) -> Optional[Violation]:
    """Check for format placeholder mismatches between msgid and msgstr.

    Args:
        entry: PO entry to check
        glossary: Optional glossary (not used by this check)

    Returns:
        Violation if format mismatch found, None otherwise
    """
    # Skip untranslated entries
    if not entry.msgstr:
        return None

    # Extract placeholders from both msgid and msgstr
    msgid_placeholders = _extract_placeholders(entry.msgid)
    msgstr_placeholders = _extract_placeholders(entry.msgstr)

    # Check for differences
    missing = msgid_placeholders - msgstr_placeholders
    extra = msgstr_placeholders - msgid_placeholders

    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(sorted(missing))}")
        if extra:
            parts.append(f"extra: {', '.join(sorted(extra))}")

        message = f"Format placeholder mismatch ({'; '.join(parts)})"

        return Violation(
            entry=entry,
            severity=Severity.ERROR,
            check_name='format_mismatch',
            message=message
        )

    return None


def _extract_placeholders(text: str) -> set:
    """Extract format placeholders from text.

    Supports both percent-style (%(name)s) and brace-style ({name}) formats.

    Args:
        text: Text to extract placeholders from

    Returns:
        Set of placeholder strings
    """
    placeholders = set()

    # Percent-style: %(name)s, %(count)d, etc.
    percent_pattern = r'%\([^)]+\)[diouxXeEfFgGcrsa%]'
    placeholders.update(re.findall(percent_pattern, text))

    # Brace-style: {0}, {name}, {}, {name:format}
    brace_pattern = r'\{[^}]*\}'
    placeholders.update(re.findall(brace_pattern, text))

    return placeholders


@registry.register('term_mismatch', Severity.WARNING)
def check_term_mismatch(
        entry: POEntryData,
        glossary: Optional[Glossary] = None
) -> Optional[Violation]:
    """Check for glossary term mismatches.

    Args:
        entry: PO entry to check
        glossary: Glossary to check against (required)

    Returns:
        Violation if term mismatch found, None otherwise
    """
    if not glossary:
        return None

    # Skip untranslated or obsolete entries
    if not entry.msgstr or entry.obsolete:
        return None

    error_msg = glossary.check_term(entry.msgid, entry.msgstr)
    if error_msg:
        return Violation(
            entry=entry,
            severity=Severity.WARNING,
            check_name='term_mismatch',
            message=error_msg
        )

    return None


def run_checks(
        entries: List[POEntryData],
        glossary: Optional[Glossary] = None,
        include_checks: Optional[List[str]] = None,
        exclude_checks: Optional[List[str]] = None
) -> List[Violation]:
    """Run all active checks on the given entries.

    Args:
        entries: List of PO entries to check
        glossary: Optional glossary for term checks
        include_checks: Optional list of check names to include
        exclude_checks: Optional list of check names to exclude

    Returns:
        List of violations found
    """
    violations = []

    # Get active checks
    active_checks = registry.get_active_checks(include_checks, exclude_checks)

    # Run checks on each entry
    for entry in entries:
        for check_name, check_data in active_checks.items():
            check_func = check_data['function']
            violation = check_func(entry, glossary)
            if violation:
                violations.append(violation)

    return violations
