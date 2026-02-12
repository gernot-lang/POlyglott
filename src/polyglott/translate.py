"""
Machine translation integration for POlyglott.

This module provides machine translation via the DeepL API, with sophisticated
placeholder protection (Strategy C: XML-wrapped placeholders) to preserve
Python format strings while maintaining correct word order in translations.

Key features:
- TranslatorBackend Protocol for extensibility (future: Google Translate, etc.)
- DeepLBackend class implementing DeepL API integration
- Placeholder protection via XML tags with ignore_tags="x"
- Ephemeral glossary support for term protection
- HTML entity handling to prevent mistranslation
- Multiline translation with line-by-line processing
- Passthrough detection for strings that don't need translation

Translation Pipeline:
    msgid → pre-filter → decode entities → split multiline
      → [for each line: tokenize → DeepL API → restore → normalize spacing]
      → rejoin multiline → re-encode entities → msgstr
"""

import html
import re
from typing import Protocol, Dict, List, Optional, Tuple

try:
    import deepl
except ImportError:
    deepl = None  # Optional dependency


# Regex patterns for placeholder detection
PERCENT_FMT = re.compile(r'%\([^)]+\)[sdif]')  # %(name)s, %(count)d, etc.
BRACE_FMT = re.compile(r'\{[^}]+\}')  # {name}, {count}, etc.


class TranslationError(Exception):
    """Raised when translation fails."""
    pass


class TranslatorBackend(Protocol):
    """
    Protocol for machine translation backends.

    This defines the interface that all translation backends must implement,
    allowing POlyglott to support multiple translation services in the future.
    """

    def translate_entry(
        self,
        msgid: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
        glossary_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Translate a single entry.

        Args:
            msgid: Source text to translate
            source_lang: Source language code (ISO 639-1)
            target_lang: Target language code (ISO 639-1)
            context: Optional context hint for translation
            glossary_entries: Optional dict of protected terms

        Returns:
            Translated text with placeholders preserved

        Raises:
            TranslationError: If translation fails
        """
        ...

    def estimate_characters(self, entries: List[str]) -> int:
        """
        Estimate total character count for translation.

        Args:
            entries: List of strings to translate

        Returns:
            Total character count
        """
        ...


def tokenize(text: str) -> Tuple[str, List[str]]:
    """
    Wrap placeholders in XML tags for DeepL protection (Strategy C).

    Replaces %(name)s and {name} placeholders with <x id="N">original</x> tags.
    DeepL's tag_handling="xml" with ignore_tags="x" preserves tag content verbatim
    AND repositions tags for correct word order.

    Args:
        text: Original text with placeholders

    Returns:
        Tuple of (wrapped_text, list_of_original_placeholders)

    Example:
        >>> tokenize("Hello %(name)s!")
        ('Hello <x id="0">%(name)s</x>!', ['%(name)s'])
    """
    placeholders = []
    placeholder_map = {}  # Map placeholder to its ID

    # Find all unique placeholders and assign IDs
    for pattern in [PERCENT_FMT, BRACE_FMT]:
        for match in pattern.finditer(text):
            placeholder = match.group(0)
            if placeholder not in placeholder_map:
                placeholder_id = len(placeholders)
                placeholder_map[placeholder] = placeholder_id
                placeholders.append(placeholder)

    # Replace all occurrences with XML tags
    wrapped = text
    for placeholder, placeholder_id in placeholder_map.items():
        wrapped = wrapped.replace(
            placeholder,
            f'<x id="{placeholder_id}">{placeholder}</x>'
        )

    return wrapped, placeholders


def restore(text: str) -> str:
    """
    Remove XML tag wrappers from placeholders.

    Strips <x id="N">...</x> tags, restoring original placeholder text.

    Args:
        text: Text with XML-wrapped placeholders

    Returns:
        Text with placeholders restored

    Example:
        >>> restore('Hello <x id="0">%(name)s</x>!')
        'Hello %(name)s!'
    """
    # Match <x id="N">content</x> and replace with just content
    pattern = re.compile(r'<x id="\d+">([^<]+)</x>')
    return pattern.sub(r'\1', text)


def escape_xml_text(text: str) -> str:
    """
    Escape XML-unsafe characters outside <x> tags.

    After tokenize() wraps placeholders in <x id="N">...</x> tags, any remaining
    &, <, or > characters in the text (outside tags) would make the XML invalid.
    This function escapes those characters to create valid XML for DeepL.

    Args:
        text: Text with <x> tags wrapping placeholders

    Returns:
        Text with XML-unsafe characters escaped outside tags

    Example:
        >>> escape_xml_text('Save <x id="0">%(name)s</x> & continue')
        'Save <x id="0">%(name)s</x> &amp; continue'
    """
    # Split on <x id="N">...</x> tags to isolate non-tag portions
    tag_pattern = re.compile(r'(<x id="\d+">[^<]+</x>)')
    parts = tag_pattern.split(text)

    # Escape XML-unsafe chars in non-tag parts only (odd indices are tags)
    escaped_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:  # Non-tag portion
            # Escape in this order to avoid double-escaping
            part = part.replace('&', '&amp;')
            part = part.replace('<', '&lt;')
            part = part.replace('>', '&gt;')
        escaped_parts.append(part)

    return ''.join(escaped_parts)


def unescape_xml_text(text: str) -> str:
    """
    Unescape XML entities after translation.

    After DeepL returns translated text with escaped entities, we need to
    restore the original characters. This is the inverse of escape_xml_text().

    CRITICAL: Unescape order matters! &amp; must be decoded LAST, otherwise
    &lt; → < followed by &amp; → & would double-decode &amp;lt; incorrectly.

    Args:
        text: Text with XML entities

    Returns:
        Text with entities unescaped

    Example:
        >>> unescape_xml_text('Save &amp; continue')
        'Save & continue'
    """
    # Unescape in reverse order: < and > first, then &
    # This prevents double-decoding of sequences like &amp;lt;
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')  # MUST be last

    return text


def normalize_spacing(text: str) -> str:
    """
    Normalize spacing around placeholders.

    DeepL sometimes adds/removes spaces around XML tags. This ensures
    consistent spacing: single space before placeholder, no extra spaces after.

    Args:
        text: Text potentially with irregular spacing

    Returns:
        Text with normalized spacing

    Example:
        >>> normalize_spacing("Hello  %(name)s  !")
        'Hello %(name)s!'
    """
    # First collapse all multiple spaces to single space
    text = re.sub(r'\s+', ' ', text)

    # Remove spaces before punctuation (whether after placeholder or not)
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)

    return text.strip()


def is_passthrough(text: str) -> bool:
    """
    Check if text should pass through without translation.

    Passthrough cases:
    - Empty or whitespace-only
    - "OK", "N/A", "—" and similar non-translatable tokens
    - Punctuation-only (., !, ?, etc.)
    - Placeholder-only (no other content)

    Args:
        text: Text to check

    Returns:
        True if text should not be translated

    Example:
        >>> is_passthrough("OK")
        True
        >>> is_passthrough("%(count)d")
        True
        >>> is_passthrough("Hello world")
        False
    """
    text = text.strip()

    # Empty or whitespace
    if not text:
        return True

    # Common non-translatable tokens
    if text.upper() in {'OK', 'N/A', '—', '–', '-', '...', '…'}:
        return True

    # Punctuation only
    if re.match(r'^[.,!?;:\-–—…\s]+$', text):
        return True

    # Remove all placeholders and check if anything remains
    remaining = PERCENT_FMT.sub('', text)
    remaining = BRACE_FMT.sub('', remaining)
    remaining = remaining.strip()

    # If only whitespace/punctuation remains, it's placeholder-only
    if not remaining or re.match(r'^[.,!?;:\-–—…\s]+$', remaining):
        return True

    return False


def protect_entities(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Decode HTML entities before translation to prevent mistranslation.

    DeepL may interpret &amp; as "and", &lt; as "less than", etc.
    We decode to actual characters, translate, then re-encode.

    Args:
        text: Text potentially containing HTML entities

    Returns:
        Tuple of (decoded_text, dict_of_entities_found)

    Example:
        >>> protect_entities("Save &amp; close")
        ('Save & close', {'&': '&amp;'})
    """
    entities = {}

    # Find all entities in original text
    entity_pattern = re.compile(r'&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;')
    for match in entity_pattern.finditer(text):
        entity = match.group(0)
        decoded = html.unescape(entity)
        if entity != decoded:  # Only track actual entities
            entities[decoded] = entity

    # Decode all entities
    decoded = html.unescape(text)

    return decoded, entities


def restore_entities(text: str, entities: Dict[str, str]) -> str:
    """
    Re-encode HTML entities after translation.

    Args:
        text: Translated text with decoded entities
        entities: Dict mapping decoded char to original entity

    Returns:
        Text with entities restored

    Example:
        >>> restore_entities("Save & close", {'&': '&amp;'})
        'Save &amp; close'
    """
    # Sort to ensure '&' is replaced FIRST to avoid double-encoding
    # We need to replace '&' → '&amp;' before replacing '<' → '&lt;',
    # otherwise we'd replace the '&' in '&lt;' giving '&amp;lt;'
    sorted_entities = sorted(entities.items(), key=lambda x: x[0] != '&')

    for decoded, entity in sorted_entities:
        text = text.replace(decoded, entity)
    return text


def translate_multiline(
    lines: List[str],
    translator_func,
    source_lang: str,
    target_lang: str,
    context: Optional[str] = None
) -> List[str]:
    """
    Translate multiline text line-by-line.

    Each line is translated separately to maintain formatting and prevent
    DeepL from reordering lines or merging paragraphs.

    Args:
        lines: List of lines to translate
        translator_func: Function that translates a single line
        source_lang: Source language code
        target_lang: Target language code
        context: Optional context hint

    Returns:
        List of translated lines
    """
    translated_lines = []

    for line in lines:
        if not line.strip():
            # Preserve empty lines
            translated_lines.append(line)
        else:
            # Translate non-empty line
            translated = translator_func(line, source_lang, target_lang, context)
            translated_lines.append(translated)

    return translated_lines


def map_language_code(code: str) -> str:
    """
    DEPRECATED: Use map_source_lang() or map_target_lang() instead.

    Map language codes to DeepL API format.

    DeepL uses ISO 639-1 codes with some exceptions:
    - "en" is ambiguous, must use "en-US" or "en-GB" for target
    - "pt" should be "pt-PT" or "pt-BR" for target

    Args:
        code: ISO 639-1 language code (de, en, fr, etc.)

    Returns:
        DeepL-compatible language code

    Example:
        >>> map_language_code("en")
        'en-US'
        >>> map_language_code("de")
        'de'
    """
    # Default mappings for ambiguous codes (prefer US English, European Portuguese)
    mappings = {
        'en': 'en-US',
        'pt': 'pt-PT',
    }

    return mappings.get(code.lower(), code)


def map_source_lang(code: str) -> str:
    """
    Map language code to DeepL source language format.

    DeepL only accepts base codes (EN, DE, FR) for source_lang.
    Regional variants (EN-US, EN-GB) are NOT accepted for source languages.

    Args:
        code: ISO 639-1 language code (de, en, fr, etc.) with optional regional variant

    Returns:
        DeepL-compatible source language code (base code, uppercased)

    Example:
        >>> map_source_lang("en")
        'EN'
        >>> map_source_lang("en-US")
        'EN'
        >>> map_source_lang("de")
        'DE'
    """
    # Strip regional variant if present (en-US → en, pt-BR → pt)
    base_code = code.split('-')[0]
    # DeepL requires uppercase for source languages
    return base_code.upper()


def map_target_lang(code: str) -> str:
    """
    Map language code to DeepL target language format.

    DeepL requires regional variants for certain target languages:
    - "en" must be "EN-US" or "EN-GB" (default: EN-US)
    - "pt" must be "PT-PT" or "PT-BR" (default: PT-PT)

    Args:
        code: ISO 639-1 language code (de, en, fr, etc.) with optional regional variant

    Returns:
        DeepL-compatible target language code (with regional variant if required)

    Example:
        >>> map_target_lang("en")
        'EN-US'
        >>> map_target_lang("en-GB")
        'EN-GB'
        >>> map_target_lang("de")
        'DE'
    """
    # If already has regional variant, preserve it (but uppercase)
    if '-' in code:
        parts = code.split('-')
        return f"{parts[0].upper()}-{parts[1].upper()}"

    # Base code without regional variant
    base_code = code.upper()

    # Default mappings for ambiguous codes (prefer US English, European Portuguese)
    mappings = {
        'EN': 'EN-US',
        'PT': 'PT-PT',
    }

    return mappings.get(base_code, base_code)


class DeepLBackend:
    """
    DeepL API integration for machine translation.

    Implements Strategy C placeholder protection:
    - Wraps placeholders in <x id="N">original</x> XML tags
    - Uses tag_handling="xml" and ignore_tags="x" API parameters
    - DeepL preserves content verbatim AND repositions for correct word order

    Features:
    - Ephemeral glossary support for term protection
    - HTML entity handling
    - Multiline translation
    - Passthrough detection
    - Graceful error handling
    """

    def __init__(self, auth_key: str):
        """
        Initialize DeepL backend.

        Args:
            auth_key: DeepL API authentication key

        Raises:
            TranslationError: If deepl package not installed or auth key invalid
        """
        if deepl is None:
            raise TranslationError(
                "DeepL support not installed. Install with: pip install 'polyglott[deepl]'"
            )

        self.translator = deepl.Translator(auth_key)
        self.glossary_id: Optional[str] = None

        # Validate auth key by checking usage (fail fast)
        try:
            self.translator.get_usage()
        except deepl.AuthorizationException:
            raise TranslationError(
                "Invalid DeepL API key. Get your key at https://www.deepl.com/pro-api\n"
                "Or set environment variable: export DEEPL_AUTH_KEY=your-key-here"
            )
        except Exception as e:
            raise TranslationError(f"Failed to initialize DeepL API: {e}")

    def translate_entry(
        self,
        msgid: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None,
        glossary_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Translate a single entry with full pipeline protection.

        Pipeline:
            1. Pre-filter: Check passthrough conditions
            2. Decode HTML entities
            3. Split multiline
            4. For each line: tokenize → DeepL API → restore → normalize spacing
            5. Rejoin multiline
            6. Re-encode HTML entities

        Args:
            msgid: Source text to translate
            source_lang: Source language code
            target_lang: Target language code
            context: Optional context hint
            glossary_entries: Optional dict of protected terms (unused, handled via glossary)

        Returns:
            Translated text with placeholders preserved

        Raises:
            TranslationError: If translation fails
        """
        # Pre-filter: passthrough strings return as-is
        if is_passthrough(msgid):
            return msgid

        # Decode HTML entities
        decoded, entities = protect_entities(msgid)

        # Handle multiline
        if '\n' in decoded:
            lines = decoded.split('\n')
            translated_lines = translate_multiline(
                lines,
                self._translate_single_line,
                source_lang,
                target_lang,
                context
            )
            result = '\n'.join(translated_lines)
        else:
            result = self._translate_single_line(decoded, source_lang, target_lang, context)

        # Re-encode HTML entities
        result = restore_entities(result, entities)

        return result

    def _translate_single_line(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[str] = None
    ) -> str:
        """
        Translate a single line with placeholder protection.

        Args:
            text: Single line to translate (no newlines)
            source_lang: Source language code
            target_lang: Target language code
            context: Optional context hint

        Returns:
            Translated line with placeholders preserved

        Raises:
            TranslationError: If API call fails
        """
        # Tokenize: wrap placeholders in XML tags
        wrapped, placeholders = tokenize(text)

        # Escape XML-unsafe characters (&, <, >) outside tags
        # This ensures valid XML for DeepL's tag_handling="xml"
        escaped = escape_xml_text(wrapped)

        # Map language codes to DeepL format
        # Source language: base code only (EN, not EN-US)
        # Target language: with regional variant if required (EN-US, not EN)
        source_lang = map_source_lang(source_lang)
        target_lang = map_target_lang(target_lang)

        # Build API parameters
        kwargs = {
            'text': escaped,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'tag_handling': 'xml',
            'ignore_tags': 'x',  # Strategy C: ignore content inside <x> tags
        }

        # Add context if available
        if context:
            kwargs['context'] = context

        # Add glossary if available
        if self.glossary_id:
            kwargs['glossary'] = self.glossary_id

        # Call DeepL API
        try:
            result = self.translator.translate_text(**kwargs)
            translated = result.text
        except deepl.QuotaExceededException:
            raise TranslationError(
                "DeepL API quota exceeded. Check your usage at https://www.deepl.com/pro-account/usage"
            )
        except Exception as e:
            raise TranslationError(f"DeepL API error: {e}")

        # Unescape XML entities before removing tags
        unescaped = unescape_xml_text(translated)

        # Restore: remove XML tag wrappers
        restored = restore(unescaped)

        # Normalize spacing around placeholders
        normalized = normalize_spacing(restored)

        return normalized

    def estimate_characters(self, entries: List[str]) -> int:
        """
        Estimate total character count for translation cost calculation.

        Args:
            entries: List of msgid strings to translate

        Returns:
            Total character count (excluding passthrough entries)
        """
        total = 0
        for entry in entries:
            if not is_passthrough(entry):
                total += len(entry)
        return total

    def create_glossary(
        self,
        terms: Dict[str, str],
        source_lang: str,
        target_lang: str,
        name: str = "polyglott_ephemeral"
    ):
        """
        Create ephemeral DeepL glossary for term protection.

        Glossaries ensure key terms are translated consistently according
        to user-provided glossary file. Glossary is ephemeral and will be
        deleted after translation completes.

        Args:
            terms: Dict mapping source terms to target translations
            source_lang: Source language code
            target_lang: Target language code
            name: Glossary name (default: polyglott_ephemeral)

        Note:
            Failures are logged but don't stop translation (graceful degradation).
            Glossary creation requires specific language pair support in DeepL.
        """
        if not terms:
            return  # No terms, skip glossary creation

        try:
            # Map language codes to DeepL format
            # Source language: base code only (EN, not EN-US)
            # Target language: with regional variant if required (EN-US, not EN)
            source_lang = map_source_lang(source_lang)
            target_lang = map_target_lang(target_lang)

            # Create glossary
            glossary = self.translator.create_glossary(
                name=name,
                source_lang=source_lang,
                target_lang=target_lang,
                entries=terms
            )
            self.glossary_id = glossary.glossary_id

        except Exception as e:
            # Graceful degradation: warn but continue without glossary
            import sys
            print(
                f"Warning: Failed to create DeepL glossary: {e}",
                file=sys.stderr
            )
            print("Continuing translation without glossary protection.", file=sys.stderr)

    def delete_glossary(self):
        """
        Delete ephemeral glossary (cleanup).

        Best-effort cleanup, never raises exceptions.
        Called in finally block to ensure cleanup even on errors.
        """
        if self.glossary_id:
            try:
                self.translator.delete_glossary(self.glossary_id)
            except Exception:
                # Best-effort cleanup, ignore failures
                pass
            finally:
                self.glossary_id = None
