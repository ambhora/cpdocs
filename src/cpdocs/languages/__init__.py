# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Programming-language adapters for extraction and presentation."""

from __future__ import annotations

import functools
import pathlib

# These three modules use nothing of this package at import time, so they may load with it.
import cpdocs.languages.base
import cpdocs.languages.kinds
import cpdocs.languages.unit


@functools.cache
def _renderings() -> dict[str, cpdocs.languages.base.LanguageRendering]:
    """The presentation rules of each semantic language.

    The language packages are imported on first use rather than with this package: their modules
    use ``cpdocs.languages`` at import time, which is only possible once this package is complete.
    """

    import cpdocs.languages.cpp.render
    import cpdocs.languages.fortran.render
    import cpdocs.languages.python.render
    import cpdocs.languages.rust.render

    return {
        "c": cpdocs.languages.cpp.render.RENDERING,
        "cpp": cpdocs.languages.cpp.render.RENDERING,
        "cuda": cpdocs.languages.cpp.render.RENDERING,
        "hip": cpdocs.languages.cpp.render.RENDERING,
        "fortran": cpdocs.languages.fortran.render.RENDERING,
        "python": cpdocs.languages.python.render.RENDERING,
        "rust": cpdocs.languages.rust.render.RENDERING,
    }


@functools.cache
def _extractors() -> dict[str, cpdocs.languages.unit.UnitExtractor]:
    """The extractor of each semantic manifest language. C, CUDA and HIP share the Clang frontend."""

    import cpdocs.languages.cpp.extract
    import cpdocs.languages.fortran.extract
    import cpdocs.languages.python.extract
    import cpdocs.languages.rust.extract

    return {
        "c": cpdocs.languages.cpp.extract.extract_unit,
        "cpp": cpdocs.languages.cpp.extract.extract_unit,
        "cuda": cpdocs.languages.cpp.extract.extract_unit,
        "hip": cpdocs.languages.cpp.extract.extract_unit,
        "fortran": cpdocs.languages.fortran.extract.extract_unit,
        "python": cpdocs.languages.python.extract.extract_unit,
        "rust": cpdocs.languages.rust.extract.extract_unit,
    }


_LANGUAGE_LABELS = {
    "c": "C",
    "cpp": "C++",
    "cuda": "CUDA",
    "hip": "HIP",
    "fortran": "Fortran",
    "python": "Python",
    "rust": "Rust",
}


def extractor_for(language: str) -> cpdocs.languages.unit.UnitExtractor:
    """Return the function that extracts manifest units of one semantic language."""

    try:
        return _extractors()[language]
    except KeyError as error:
        raise ValueError(f"unsupported API language: {language}") from error


def rendering_for(language: str) -> cpdocs.languages.base.LanguageRendering:
    """Return rendering semantics for one programming language."""

    try:
        return _renderings()[language]
    except KeyError as error:
        raise ValueError(f"unsupported API language: {language}") from error


def language_label(language: str) -> str:
    return _LANGUAGE_LABELS.get(language, language)


def entity_kind(language: str, kind: str) -> cpdocs.languages.kinds.EntityKind:
    """The declaration of ``kind`` in the kind table of ``language``.

    Raises ``ValueError`` for an unknown language and ``KeyError`` for a kind the language does
    not declare.
    """

    return rendering_for(language).kinds[kind]


def kind_label(kind: str, language: str) -> str:
    """The name of a kind shown to readers, such as ``type alias``."""

    return entity_kind(language, kind).label


def kind_marker(kind: str, language: str) -> str:
    """The letter on the badge of a kind."""

    return entity_kind(language, kind).marker


def source_language(path: str) -> str:
    suffix = pathlib.Path(path).suffix.casefold()
    if suffix in {".cu", ".cuh"}:
        return "cuda"
    if suffix == ".hip":
        return "hip"
    if suffix in {".c"}:
        return "c"
    if suffix in {".h", ".hh", ".hpp", ".hxx", ".cc", ".cpp", ".cxx"}:
        return "cpp"
    for language in ("fortran", "python", "rust"):
        if suffix in _renderings()[language].source_suffixes:
            return language
    return "text"


__all__ = [
    "entity_kind",
    "extractor_for",
    "kind_label",
    "kind_marker",
    "language_label",
    "rendering_for",
    "source_language",
]
