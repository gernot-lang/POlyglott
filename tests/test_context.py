"""Tests for context inference module."""

import pytest
from pathlib import Path

from polyglott.context import (
    load_context_rules,
    load_preset,
    match_context,
    PRESETS
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLoadContextRules:
    """Test suite for load_context_rules function."""

    def test_load_valid_rules(self):
        """Test loading a valid YAML rules file."""
        rules = load_context_rules(FIXTURES_DIR / "context_rules.yaml")

        assert len(rules) == 6
        assert rules[0] == {"pattern": "tables.py", "context": "column_header"}
        assert rules[1] == {"pattern": "forms.py", "context": "form_label"}
        assert rules[5] == {"pattern": "sidebar", "context": "navigation"}

    def test_missing_file(self):
        """Test error on missing file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_context_rules(FIXTURES_DIR / "nonexistent.yaml")
        assert "not found" in str(exc_info.value)

    def test_malformed_yaml(self):
        """Test error on malformed YAML."""
        with pytest.raises(ValueError) as exc_info:
            load_context_rules(FIXTURES_DIR / "context_invalid.yaml")
        assert "Invalid YAML" in str(exc_info.value)

    def test_missing_rules_key(self):
        """Test error on YAML without 'rules' key."""
        with pytest.raises(ValueError) as exc_info:
            load_context_rules(FIXTURES_DIR / "context_no_rules.yaml")
        assert "'rules'" in str(exc_info.value)

    def test_missing_pattern_field(self):
        """Test error on rule missing 'pattern' field."""
        with pytest.raises(ValueError) as exc_info:
            load_context_rules(FIXTURES_DIR / "context_missing_pattern.yaml")
        assert "pattern" in str(exc_info.value)

    def test_missing_context_field(self):
        """Test error on rule missing 'context' field."""
        with pytest.raises(ValueError) as exc_info:
            load_context_rules(FIXTURES_DIR / "context_missing_context.yaml")
        assert "context" in str(exc_info.value)


class TestLoadPreset:
    """Test suite for load_preset function."""

    def test_load_django_preset(self):
        """Test loading the Django preset."""
        rules = load_preset('django')

        assert len(rules) > 0
        assert isinstance(rules, list)
        assert all('pattern' in rule and 'context' in rule for rule in rules)

        # Check some expected patterns
        patterns = [rule['pattern'] for rule in rules]
        assert 'forms.py' in patterns
        assert 'models.py' in patterns

    def test_unknown_preset(self):
        """Test error on unknown preset name."""
        with pytest.raises(ValueError) as exc_info:
            load_preset('nonexistent')
        assert "Unknown preset" in str(exc_info.value)
        assert "Available presets" in str(exc_info.value)

    def test_presets_dict_not_empty(self):
        """Test that PRESETS dict contains at least django."""
        assert 'django' in PRESETS
        assert isinstance(PRESETS['django'], list)


class TestMatchContext:
    """Test suite for match_context function."""

    def test_single_reference_matches_first_rule(self):
        """Test reference matches first rule."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
        ]
        context, sources = match_context('myapp/forms.py:10', rules)

        assert context == 'form_label'
        assert sources == ''

    def test_single_reference_matches_second_rule(self):
        """Test reference matches second rule when first doesn't match."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
        ]
        context, sources = match_context('myapp/models.py:25', rules)

        assert context == 'field_label'
        assert sources == ''

    def test_no_rule_matches(self):
        """Test no rule matches returns empty context."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        context, sources = match_context('myapp/unknown.py:10', rules)

        assert context == ''
        assert sources == ''

    def test_rule_order_matters(self):
        """Test rule order matters - first match wins."""
        rules = [
            {'pattern': 'app/', 'context': 'generic'},
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        # 'app/' matches first, so should return 'generic'
        context, sources = match_context('myapp/forms.py:10', rules)

        assert context == 'generic'
        assert sources == ''

    def test_line_number_stripped(self):
        """Test line number is correctly stripped from reference."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        context, sources = match_context('myapp/forms.py:12345', rules)

        assert context == 'form_label'
        assert sources == ''

    def test_multiple_references_same_context(self):
        """Test all references match same context."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        context, sources = match_context('myapp/forms.py:10 myapp/forms.py:20', rules)

        assert context == 'form_label'
        assert sources == ''  # Unanimous, so sources is empty

    def test_multiple_references_clear_majority(self):
        """Test clear majority context wins."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
        ]
        # 2 form_label, 1 field_label -> form_label wins
        context, sources = match_context(
            'myapp/forms.py:10 myapp/forms.py:20 myapp/models.py:30',
            rules
        )

        assert context == 'form_label'
        assert sources != ''  # Should be populated
        assert 'myapp/forms.py=form_label' in sources
        assert 'myapp/models.py=field_label' in sources

    def test_multiple_references_tie(self):
        """Test tie results in 'ambiguous'."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
        ]
        # 1 form_label, 1 field_label -> tie
        context, sources = match_context(
            'myapp/forms.py:10 myapp/models.py:30',
            rules
        )

        assert context == 'ambiguous'
        assert sources != ''
        assert 'myapp/forms.py=form_label' in sources
        assert 'myapp/models.py=field_label' in sources

    def test_multiple_references_three_way_tie(self):
        """Test three-way tie results in 'ambiguous'."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
            {'pattern': 'views.py', 'context': 'message'},
        ]
        # 1 of each -> three-way tie
        context, sources = match_context(
            'forms.py:1 models.py:2 views.py:3',
            rules
        )

        assert context == 'ambiguous'
        assert sources != ''

    def test_mixed_matched_and_unmatched(self):
        """Test mix of matched and unmatched references."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        # Only forms.py matches, unknown.py doesn't
        context, sources = match_context(
            'myapp/forms.py:10 myapp/unknown.py:20',
            rules
        )

        # Only matched reference counts
        assert context == 'form_label'
        assert sources == ''  # Only one matched context

    def test_empty_references(self):
        """Test entry with no references."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        context, sources = match_context('', rules)

        assert context == ''
        assert sources == ''

    def test_whitespace_only_references(self):
        """Test entry with whitespace-only references."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        context, sources = match_context('   ', rules)

        assert context == ''
        assert sources == ''

    def test_empty_rules_list(self):
        """Test empty rules list returns empty context."""
        context, sources = match_context('myapp/forms.py:10', [])

        assert context == ''
        assert sources == ''

    def test_context_sources_format(self):
        """Test context_sources format is correct."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
            {'pattern': 'models.py', 'context': 'field_label'},
        ]
        context, sources = match_context(
            'app/forms.py:10 app/models.py:20',
            rules
        )

        # Should be semicolon-separated filepath=context pairs
        assert ';' in sources
        parts = sources.split(';')
        assert len(parts) == 2
        assert 'app/forms.py=form_label' in parts
        assert 'app/models.py=field_label' in parts

    def test_substring_matching(self):
        """Test that pattern matching is substring-based."""
        rules = [
            {'pattern': 'forms/', 'context': 'form_label'},
        ]
        # Should match any path containing 'forms/'
        context, sources = match_context('myapp/forms/user_forms.py:10', rules)

        assert context == 'form_label'
        assert sources == ''

    def test_multiple_colons_in_reference(self):
        """Test handling of file paths with colons."""
        rules = [
            {'pattern': 'forms.py', 'context': 'form_label'},
        ]
        # Edge case: what if filepath itself contains colons?
        # We strip from the RIGHT-most colon
        context, sources = match_context('path:with:colons/forms.py:10', rules)

        assert context == 'form_label'
        assert sources == ''
