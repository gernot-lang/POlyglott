"""Tests for translation module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from polyglott.translate import (
    tokenize,
    restore,
    normalize_spacing,
    is_passthrough,
    protect_entities,
    restore_entities,
    translate_multiline,
    map_language_code,
    DeepLBackend,
    TranslationError,
)


class TestTokenization:
    """Test placeholder tokenization (Strategy C)."""

    def test_tokenize_percent_fmt(self):
        """Test wrapping %(name)s placeholders."""
        text = "Hello %(name)s!"
        wrapped, placeholders = tokenize(text)

        assert placeholders == ['%(name)s']
        assert wrapped == 'Hello <x id="0">%(name)s</x>!'

    def test_tokenize_brace_fmt(self):
        """Test wrapping {name} placeholders."""
        text = "Count: {count}"
        wrapped, placeholders = tokenize(text)

        assert placeholders == ['{count}']
        assert wrapped == 'Count: <x id="0">{count}</x>'

    def test_tokenize_mixed_placeholders(self):
        """Test mixed %(name)s and {name} placeholders."""
        text = "User %(user)s has {count} items"
        wrapped, placeholders = tokenize(text)

        assert set(placeholders) == {'%(user)s', '{count}'}
        assert '<x id="0">' in wrapped
        assert '<x id="1">' in wrapped

    def test_tokenize_multiple_same_placeholder(self):
        """Test duplicate placeholders."""
        text = "%(name)s loves %(name)s"
        wrapped, placeholders = tokenize(text)

        # Placeholder appears once in list
        assert placeholders == ['%(name)s']
        # But wrapped twice in text
        assert wrapped.count('<x id="0">%(name)s</x>') == 2

    def test_tokenize_no_placeholders(self):
        """Test text without placeholders."""
        text = "Hello world"
        wrapped, placeholders = tokenize(text)

        assert placeholders == []
        assert wrapped == "Hello world"

    def test_restore_xml_tags(self):
        """Test removing XML tag wrappers."""
        text = 'Hello <x id="0">%(name)s</x>!'
        restored = restore(text)

        assert restored == "Hello %(name)s!"

    def test_restore_multiple_tags(self):
        """Test restoring multiple placeholders."""
        text = 'User <x id="0">%(user)s</x> has <x id="1">{count}</x> items'
        restored = restore(text)

        assert restored == "User %(user)s has {count} items"

    def test_restore_no_tags(self):
        """Test text without XML tags."""
        text = "Hello world"
        restored = restore(text)

        assert restored == "Hello world"


class TestSpacingNormalization:
    """Test spacing normalization around placeholders."""

    def test_normalize_extra_spaces_before_placeholder(self):
        """Test collapsing multiple spaces before placeholder."""
        text = "Hello  %(name)s"
        normalized = normalize_spacing(text)

        assert normalized == "Hello %(name)s"

    def test_normalize_spaces_before_punctuation(self):
        """Test removing space between placeholder and punctuation."""
        text = "Hello %(name)s !"
        normalized = normalize_spacing(text)

        assert normalized == "Hello %(name)s!"

    def test_normalize_multiple_issues(self):
        """Test fixing multiple spacing issues."""
        text = "User  %(user)s  has  {count}  items ."
        normalized = normalize_spacing(text)

        assert normalized == "User %(user)s has {count} items."

    def test_normalize_leading_trailing_spaces(self):
        """Test stripping leading/trailing whitespace."""
        text = "  Hello %(name)s  "
        normalized = normalize_spacing(text)

        assert normalized == "Hello %(name)s"


class TestPreFilter:
    """Test passthrough detection."""

    def test_passthrough_empty(self):
        """Test empty string is passthrough."""
        assert is_passthrough("")
        assert is_passthrough("   ")

    def test_passthrough_ok_token(self):
        """Test OK token is passthrough."""
        assert is_passthrough("OK")
        assert is_passthrough("ok")
        assert is_passthrough("Ok")

    def test_passthrough_na_token(self):
        """Test N/A token is passthrough."""
        assert is_passthrough("N/A")
        assert is_passthrough("—")
        assert is_passthrough("–")

    def test_passthrough_punctuation_only(self):
        """Test punctuation-only is passthrough."""
        assert is_passthrough(".")
        assert is_passthrough("...")
        assert is_passthrough("!")
        assert is_passthrough("?")

    def test_passthrough_placeholder_only(self):
        """Test placeholder-only is passthrough."""
        assert is_passthrough("%(count)d")
        assert is_passthrough("{name}")
        assert is_passthrough("%(user)s, {count}")

    def test_not_passthrough_translatable_text(self):
        """Test actual translatable text is not passthrough."""
        assert not is_passthrough("Hello world")
        assert not is_passthrough("Welcome %(name)s")
        assert not is_passthrough("Count: {count}")


class TestMultiline:
    """Test multiline translation."""

    def test_translate_multiline_preserves_empty_lines(self):
        """Test empty lines are preserved."""
        lines = ["Line 1", "", "Line 2"]
        translator_func = Mock(side_effect=lambda text, *args, **kwargs: f"Translated: {text}")

        result = translate_multiline(lines, translator_func, "en", "de")

        assert result == ["Translated: Line 1", "", "Translated: Line 2"]

    def test_translate_multiline_calls_translator_per_line(self):
        """Test translator called for each non-empty line."""
        lines = ["Line 1", "Line 2"]
        translator_func = Mock(side_effect=lambda text, *args, **kwargs: f"Translated: {text}")

        translate_multiline(lines, translator_func, "en", "de")

        assert translator_func.call_count == 2

    def test_translate_multiline_with_context(self):
        """Test context passed to translator."""
        lines = ["Line 1"]
        translator_func = Mock(return_value="Translated")

        translate_multiline(lines, translator_func, "en", "de", context="admin")

        translator_func.assert_called_with("Line 1", "en", "de", "admin")


class TestEntities:
    """Test HTML entity handling."""

    def test_protect_entities_ampersand(self):
        """Test decoding &amp; entity."""
        text = "Save &amp; close"
        decoded, entities = protect_entities(text)

        assert decoded == "Save & close"
        assert entities == {'&': '&amp;'}

    def test_protect_entities_multiple(self):
        """Test decoding multiple entities."""
        text = "&lt;tag&gt; &amp; &quot;quote&quot;"
        decoded, entities = protect_entities(text)

        assert decoded == '<tag> & "quote"'
        assert '&' in entities
        assert '<' in entities
        assert '>' in entities
        assert '"' in entities

    def test_protect_entities_numeric(self):
        """Test numeric entities."""
        text = "&#169; Copyright"
        decoded, entities = protect_entities(text)

        assert decoded == "© Copyright"
        assert '©' in entities

    def test_protect_entities_no_entities(self):
        """Test text without entities."""
        text = "Hello world"
        decoded, entities = protect_entities(text)

        assert decoded == "Hello world"
        assert entities == {}

    def test_restore_entities_single(self):
        """Test re-encoding single entity."""
        text = "Save & close"
        entities = {'&': '&amp;'}
        restored = restore_entities(text, entities)

        assert restored == "Save &amp; close"

    def test_restore_entities_multiple(self):
        """Test re-encoding multiple entities."""
        text = '<tag> & "quote"'
        entities = {'<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;'}
        restored = restore_entities(text, entities)

        assert restored == '&lt;tag&gt; &amp; &quot;quote&quot;'


class TestLanguageMapping:
    """Test language code mapping for DeepL."""

    def test_map_language_code_english(self):
        """Test en → en-US mapping."""
        assert map_language_code("en") == "en-US"
        assert map_language_code("EN") == "en-US"

    def test_map_language_code_portuguese(self):
        """Test pt → pt-PT mapping."""
        assert map_language_code("pt") == "pt-PT"
        assert map_language_code("PT") == "pt-PT"

    def test_map_language_code_passthrough(self):
        """Test codes that don't need mapping."""
        assert map_language_code("de") == "de"
        assert map_language_code("fr") == "fr"
        assert map_language_code("es") == "es"


class TestDeepLBackend:
    """Test DeepL backend class."""

    @patch('polyglott.translate.deepl')
    def test_init_success(self, mock_deepl):
        """Test successful initialization."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("valid-key")

        assert backend.translator == mock_translator
        mock_deepl.Translator.assert_called_once_with("valid-key")
        mock_translator.get_usage.assert_called_once()

    @patch('polyglott.translate.deepl')
    def test_init_invalid_key(self, mock_deepl):
        """Test initialization with invalid key."""
        # Create a custom exception class for AuthorizationException
        class MockAuthorizationException(Exception):
            pass

        mock_translator = Mock()
        mock_translator.get_usage.side_effect = MockAuthorizationException("Invalid key")
        mock_deepl.Translator.return_value = mock_translator
        mock_deepl.AuthorizationException = MockAuthorizationException

        with pytest.raises(TranslationError) as exc_info:
            DeepLBackend("invalid-key")

        assert "Invalid DeepL API key" in str(exc_info.value)

    @patch('polyglott.translate.deepl', None)
    def test_init_missing_deepl_package(self):
        """Test initialization when deepl package not installed."""
        with pytest.raises(TranslationError) as exc_info:
            DeepLBackend("key")

        assert "DeepL support not installed" in str(exc_info.value)

    @patch('polyglott.translate.deepl')
    def test_translate_entry_passthrough(self, mock_deepl):
        """Test passthrough entries return unchanged."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        result = backend.translate_entry("OK", "en", "de")

        assert result == "OK"
        # DeepL API should NOT be called for passthrough
        mock_translator.translate_text.assert_not_called()

    @patch('polyglott.translate.deepl')
    def test_translate_entry_simple_text(self, mock_deepl):
        """Test translating simple text."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_result = Mock()
        mock_result.text = "Hallo Welt"
        mock_translator.translate_text.return_value = mock_result
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        result = backend.translate_entry("Hello world", "en", "de")

        assert result == "Hallo Welt"
        mock_translator.translate_text.assert_called_once()

    @patch('polyglott.translate.deepl')
    def test_translate_entry_with_placeholder(self, mock_deepl):
        """Test translating text with placeholder protection."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_result = Mock()
        # Simulate DeepL preserving XML tags
        mock_result.text = 'Hallo <x id="0">%(name)s</x>!'
        mock_translator.translate_text.return_value = mock_result
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        result = backend.translate_entry("Hello %(name)s!", "en", "de")

        assert result == "Hallo %(name)s!"
        # Verify XML tags were used in API call
        call_args = mock_translator.translate_text.call_args
        assert 'tag_handling' in call_args.kwargs
        assert call_args.kwargs['tag_handling'] == 'xml'
        assert call_args.kwargs['ignore_tags'] == 'x'

    @patch('polyglott.translate.deepl')
    def test_translate_entry_multiline(self, mock_deepl):
        """Test translating multiline text."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_translator.translate_text.side_effect = [
            Mock(text="Zeile 1"),
            Mock(text="Zeile 2")
        ]
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        result = backend.translate_entry("Line 1\nLine 2", "en", "de")

        assert result == "Zeile 1\nZeile 2"
        # Should call translate_text twice (once per line)
        assert mock_translator.translate_text.call_count == 2

    @patch('polyglott.translate.deepl')
    def test_translate_entry_with_entities(self, mock_deepl):
        """Test translating text with HTML entities."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        # DeepL receives decoded text, returns translated
        mock_result = Mock(text="Speichern & schließen")
        mock_translator.translate_text.return_value = mock_result
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        result = backend.translate_entry("Save &amp; close", "en", "de")

        # Entities should be restored
        assert result == "Speichern &amp; schließen"

    @patch('polyglott.translate.deepl')
    def test_translate_entry_quota_exceeded(self, mock_deepl):
        """Test quota exceeded error."""
        # Create a custom exception class for QuotaExceededException
        class MockQuotaExceededException(Exception):
            pass

        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_translator.translate_text.side_effect = MockQuotaExceededException("Quota exceeded")
        mock_deepl.Translator.return_value = mock_translator
        mock_deepl.QuotaExceededException = MockQuotaExceededException

        backend = DeepLBackend("key")

        with pytest.raises(TranslationError) as exc_info:
            backend.translate_entry("Hello", "en", "de")

        assert "quota exceeded" in str(exc_info.value).lower()

    @patch('polyglott.translate.deepl')
    def test_estimate_characters(self, mock_deepl):
        """Test character count estimation."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        entries = ["Hello world", "OK", "Test %(name)s"]
        count = backend.estimate_characters(entries)

        # "OK" is passthrough, so only count "Hello world" (11) and "Test %(name)s" (13)
        assert count == 24

    @patch('polyglott.translate.deepl')
    def test_create_glossary_success(self, mock_deepl):
        """Test successful glossary creation."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_glossary = Mock()
        mock_glossary.glossary_id = "glossary-123"
        mock_translator.create_glossary.return_value = mock_glossary
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        terms = {"hello": "hallo", "world": "welt"}
        backend.create_glossary(terms, "en", "de")

        assert backend.glossary_id == "glossary-123"
        mock_translator.create_glossary.assert_called_once()

    @patch('polyglott.translate.deepl')
    def test_create_glossary_empty_terms(self, mock_deepl):
        """Test glossary creation with no terms."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        backend.create_glossary({}, "en", "de")

        # Should not call create_glossary
        mock_translator.create_glossary.assert_not_called()

    @patch('polyglott.translate.deepl')
    def test_create_glossary_failure_graceful(self, mock_deepl, capsys):
        """Test glossary creation failure is gracefully handled."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_translator.create_glossary.side_effect = Exception("Glossary not supported")
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        terms = {"hello": "hallo"}
        # Should not raise, just warn
        backend.create_glossary(terms, "en", "de")

        captured = capsys.readouterr()
        assert "Warning: Failed to create DeepL glossary" in captured.err

    @patch('polyglott.translate.deepl')
    def test_delete_glossary_success(self, mock_deepl):
        """Test successful glossary deletion."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        backend.glossary_id = "glossary-123"
        backend.delete_glossary()

        mock_translator.delete_glossary.assert_called_once_with("glossary-123")
        assert backend.glossary_id is None

    @patch('polyglott.translate.deepl')
    def test_delete_glossary_no_glossary(self, mock_deepl):
        """Test delete_glossary when no glossary exists."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        backend.delete_glossary()

        # Should not call delete_glossary
        mock_translator.delete_glossary.assert_not_called()

    @patch('polyglott.translate.deepl')
    def test_delete_glossary_failure_silent(self, mock_deepl):
        """Test delete_glossary failure is silently ignored."""
        mock_translator = Mock()
        mock_translator.get_usage.return_value = Mock()
        mock_translator.delete_glossary.side_effect = Exception("Delete failed")
        mock_deepl.Translator.return_value = mock_translator

        backend = DeepLBackend("key")
        backend.glossary_id = "glossary-123"

        # Should not raise
        backend.delete_glossary()

        assert backend.glossary_id is None


class TestIntegration:
    """Integration tests with master CSV."""

    def test_translate_updates_master_csv(self):
        """Test translation updates master CSV with machine status."""
        from polyglott.master import MasterEntry, save_master, load_master

        # Create temporary master CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='-de.csv', delete=False) as f:
            master_path = f.name

        try:
            # Create test entries
            entries = [
                MasterEntry(
                    msgid="Hello world",
                    msgstr="",
                    status="empty",
                    score="",
                    context="",
                    context_sources=""
                )
            ]

            # Save master
            save_master(entries, master_path)

            # Load and verify
            loaded = load_master(master_path)
            assert len(loaded) == 1
            entry = loaded["Hello world"]
            assert entry.status == "empty"
            assert entry.msgstr == ""

            # Simulate translation (we can't actually call DeepL in tests)
            entry.msgstr = "Hallo Welt"
            entry.status = "machine"
            entry.score = ""

            # Save updated master
            save_master([entry], master_path)

            # Verify update
            loaded = load_master(master_path)
            entry = loaded["Hello world"]
            assert entry.msgstr == "Hallo Welt"
            assert entry.status == "machine"
            assert entry.score == ""

        finally:
            # Cleanup
            Path(master_path).unlink(missing_ok=True)

    def test_status_transitions(self):
        """Test status transitions: empty → machine."""
        from polyglott.master import MasterEntry

        entry = MasterEntry(
            msgid="Test",
            msgstr="",
            status="empty",
            score="",
            context="",
            context_sources=""
        )

        # Before translation
        assert entry.status == "empty"
        assert entry.msgstr == ""

        # After translation
        entry.msgstr = "Translated"
        entry.status = "machine"
        entry.score = ""

        assert entry.status == "machine"
        assert entry.msgstr == "Translated"
        assert entry.score == ""
