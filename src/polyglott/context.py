"""Context inference from PO file source references."""

from collections import Counter
from pathlib import Path
from typing import List, Tuple, Dict, Any

import yaml

# Built-in presets
PRESETS = {
    'django': [
        {'pattern': 'tables.py', 'context': 'column_header'},
        {'pattern': 'forms.py', 'context': 'form_label'},
        {'pattern': 'forms/', 'context': 'form_label'},
        {'pattern': 'models.py', 'context': 'field_label'},
        {'pattern': 'serializers.py', 'context': 'field_label'},
        {'pattern': 'views.py', 'context': 'message'},
        {'pattern': 'management/commands/', 'context': 'log_message'},
        {'pattern': 'admin.py', 'context': 'admin'},
        {'pattern': 'sidebar', 'context': 'navigation'},
        {'pattern': 'navbar', 'context': 'navigation'},
        {'pattern': 'templates/', 'context': 'template'},
    ]
}


def load_context_rules(path: str) -> List[Dict[str, str]]:
    """Load context rules from a YAML file.

    Args:
        path: Path to the YAML rules file

    Returns:
        List of rule dictionaries with 'pattern' and 'context' keys

    Raises:
        FileNotFoundError: If the rules file doesn't exist
        ValueError: If the YAML is malformed or missing required fields
    """
    rules_path = Path(path)
    if not rules_path.exists():
        raise FileNotFoundError(f"Context rules file not found: {path}")

    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in context rules file: {e}")

    if not isinstance(data, dict):
        raise ValueError("Context rules file must contain a YAML dictionary")

    if 'rules' not in data:
        raise ValueError("Context rules file must contain a 'rules' key")

    rules = data['rules']
    if not isinstance(rules, list):
        raise ValueError("'rules' must be a list")

    # Validate each rule
    validated_rules = []
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"Rule {i} must be a dictionary")

        if 'pattern' not in rule:
            raise ValueError(f"Rule {i} is missing 'pattern' field")

        if 'context' not in rule:
            raise ValueError(f"Rule {i} is missing 'context' field")

        if not isinstance(rule['pattern'], str):
            raise ValueError(f"Rule {i} 'pattern' must be a string")

        if not isinstance(rule['context'], str):
            raise ValueError(f"Rule {i} 'context' must be a string")

        validated_rules.append({
            'pattern': rule['pattern'],
            'context': rule['context']
        })

    return validated_rules


def load_preset(name: str) -> List[Dict[str, str]]:
    """Load a built-in preset by name.

    Args:
        name: Preset name (e.g., 'django')

    Returns:
        List of rule dictionaries

    Raises:
        ValueError: If the preset name is not recognized
    """
    if name not in PRESETS:
        available = ', '.join(PRESETS.keys())
        raise ValueError(f"Unknown preset '{name}'. Available presets: {available}")

    return PRESETS[name]


def match_context(references: str, rules: List[Dict[str, str]]) -> Tuple[str, str]:
    """Match references against context rules and determine context.

    Args:
        references: Space-separated string of filepath:lineno references
        rules: List of rule dictionaries with 'pattern' and 'context'

    Returns:
        Tuple of (context, context_sources)
        - context: The determined context label, 'ambiguous', or empty string
        - context_sources: Semicolon-separated filepath=context pairs (only when ambiguous)

    Matching logic:
        1. Unanimous: all references -> same context => that context, empty sources
        2. Majority: one context appears most => majority context, populated sources
        3. Tie: no clear majority => 'ambiguous', populated sources
        4. No match: no references match any rule => empty string, empty sources
        5. No references: references string is empty => empty string, empty sources
    """
    # Handle empty references
    if not references or not references.strip():
        return ('', '')

    # Parse references into list of filepaths
    ref_list = references.strip().split()
    filepaths = []
    for ref in ref_list:
        # Strip :lineno suffix
        if ':' in ref:
            filepath = ref.rsplit(':', 1)[0]
            filepaths.append(filepath)

    if not filepaths:
        return ('', '')

    # Match each filepath against rules
    matched_contexts = []
    filepath_context_map = {}

    for filepath in filepaths:
        matched_context = _match_single_reference(filepath, rules)
        if matched_context:
            matched_contexts.append(matched_context)
            filepath_context_map[filepath] = matched_context

    # No matches at all
    if not matched_contexts:
        return ('', '')

    # Count occurrences of each context
    context_counts = Counter(matched_contexts)
    unique_contexts = list(context_counts.keys())

    # Unanimous: all references match the same context
    if len(unique_contexts) == 1:
        return (unique_contexts[0], '')

    # Multiple contexts: determine majority or ambiguous
    max_count = max(context_counts.values())
    contexts_with_max = [ctx for ctx, count in context_counts.items() if count == max_count]

    # Build context_sources string
    context_sources_list = [f"{fp}={ctx}" for fp, ctx in filepath_context_map.items()]
    context_sources = ';'.join(context_sources_list)

    if len(contexts_with_max) == 1:
        # Clear majority
        return (contexts_with_max[0], context_sources)
    else:
        # Tie
        return ('ambiguous', context_sources)


def _match_single_reference(filepath: str, rules: List[Dict[str, str]]) -> str:
    """Match a single filepath against rules.

    Args:
        filepath: File path to match
        rules: List of rule dictionaries

    Returns:
        Context string if matched, empty string otherwise
    """
    for rule in rules:
        pattern = rule['pattern']
        if pattern in filepath:
            return rule['context']
    return ''
