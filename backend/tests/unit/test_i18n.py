"""i18n consistency: every supported language is fully wired on the backend."""

from __future__ import annotations

from src.services.llm_service import _LANG_NAMES
from src.services.qa_service import _TEMPLATES
from src.services.request_context import SUPPORTED_LANGUAGES


def test_every_supported_language_has_all_qa_templates():
    expected_keys = set(_TEMPLATES["en"])
    for lang in SUPPORTED_LANGUAGES:
        assert lang in _TEMPLATES, f"qa_service._TEMPLATES missing '{lang}'"
        assert set(_TEMPLATES[lang]) == expected_keys, f"template keys differ for '{lang}'"


def test_templates_keep_placeholders_intact():
    # Figures are interpolated by code; a translation must not drop or rename
    # the placeholders or .format() would crash / silently omit the number.
    import re

    for lang, templates in _TEMPLATES.items():
        for key, text in templates.items():
            for placeholder in re.findall(r"\{(\w+)\}", _TEMPLATES["en"][key]):
                assert f"{{{placeholder}}}" in text, (
                    f"'{lang}.{key}' lost placeholder {{{placeholder}}}"
                )


def test_llm_language_clause_covers_all_non_english_languages():
    missing = [l for l in SUPPORTED_LANGUAGES if l != "en" and l not in _LANG_NAMES]
    assert not missing, f"llm_service._LANG_NAMES missing: {missing}"


def test_no_stray_languages_outside_supported_set():
    assert set(_TEMPLATES) <= set(SUPPORTED_LANGUAGES)
    assert set(_LANG_NAMES) <= set(SUPPORTED_LANGUAGES)
