from __future__ import annotations

from typing import Protocol


class TranslationError(RuntimeError):
    """Raised when a configured translation provider cannot translate text."""


class TextTranslator(Protocol):
    def translate(self, text: str, source_language: str, target_language: str) -> str: ...


class ArgosTextTranslator:
    """Offline translation through an installed Argos language package."""

    def translate(self, text: str, source_language: str = "en", target_language: str = "he") -> str:
        if not text.strip():
            return text

        try:
            import argostranslate.translate
        except ImportError as exc:
            raise TranslationError(
                "Argos Translate is not installed; install the mosaic-server dependencies"
            ) from exc

        try:
            installed_languages = argostranslate.translate.get_installed_languages()
            source = next(
                language for language in installed_languages if language.code == source_language
            )
            target = next(
                language for language in installed_languages if language.code == target_language
            )
            translation = source.get_translation(target)
            translated = translation.translate(text).strip()
        except (StopIteration, AttributeError, RuntimeError) as exc:
            raise TranslationError(
                f"Argos language package {source_language}->{target_language} is not installed"
            ) from exc

        if not translated:
            raise TranslationError("Argos Translate returned an empty translation")
        return translated
