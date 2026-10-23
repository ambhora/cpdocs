# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Programming-language adapters for extraction and presentation."""

from __future__ import annotations

from pathlib import Path

from .base import LanguageRendering
from .cpp.extract import extract_unit as _extract_c_family
from .cpp.render import RENDERING as CPP
from .fortran.extract import extract_unit as _extract_fortran
from .fortran.render import RENDERING as FORTRAN
from .kinds import EntityKind, EntityKinds, Role
from .python.extract import extract_unit as _extract_python
from .python.render import RENDERING as PYTHON
from .rust.extract import extract_unit as _extract_rust
from .rust.render import RENDERING as RUST
from .unit import UnitContext, UnitExtractor

_RENDERINGS = {"c": CPP, "cpp": CPP, "cuda": CPP, "hip": CPP, "fortran": FORTRAN, "python": PYTHON, "rust": RUST}

# The extractor of each semantic manifest language. C, CUDA and HIP units share the Clang frontend.
_EXTRACTORS: dict[str, UnitExtractor] = {
    "c": _extract_c_family,
    "cpp": _extract_c_family,
    "cuda": _extract_c_family,
    "hip": _extract_c_family,
    "fortran": _extract_fortran,
    "python": _extract_python,
    "rust": _extract_rust,
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


def extractor_for(language: str) -> UnitExtractor:
    """Return the function that extracts manifest units of one semantic language."""

    try:
        return _EXTRACTORS[language]
    except KeyError as error:
        raise ValueError(f"unsupported API language: {language}") from error


def rendering_for(language: str) -> LanguageRendering:
    """Return rendering semantics for one programming language."""

    try:
        return _RENDERINGS[language]
    except KeyError as error:
        raise ValueError(f"unsupported API language: {language}") from error


def language_label(language: str) -> str:
    return _LANGUAGE_LABELS.get(language, language)


def entity_kind(language: str, kind: str) -> EntityKind:
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
    suffix = Path(path).suffix.casefold()
    if suffix in {".cu", ".cuh"}:
        return "cuda"
    if suffix == ".hip":
        return "hip"
    if suffix in {".c"}:
        return "c"
    if suffix in {".h", ".hh", ".hpp", ".hxx", ".cc", ".cpp", ".cxx"}:
        return "cpp"
    for language in ("fortran", "python", "rust"):
        if suffix in _RENDERINGS[language].source_suffixes:
            return language
    return "text"


__all__ = [
    "EntityKind",
    "EntityKinds",
    "LanguageRendering",
    "Role",
    "UnitContext",
    "UnitExtractor",
    "entity_kind",
    "extractor_for",
    "kind_label",
    "kind_marker",
    "language_label",
    "rendering_for",
    "source_language",
]
