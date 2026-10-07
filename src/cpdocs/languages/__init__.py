# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Programming-language adapters for extraction and presentation."""

from __future__ import annotations

from pathlib import Path

from .base import LanguageRendering
from .cpp.render import RENDERING as CPP
from .fortran.render import RENDERING as FORTRAN
from .python.render import RENDERING as PYTHON
from .rust.render import RENDERING as RUST

_RENDERINGS = {
    "c": CPP,
    "cpp": CPP,
    "cuda": CPP,
    "hip": CPP,
    "fortran": FORTRAN,
    "python": PYTHON,
    "rust": RUST,
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

_KIND_LABELS = {
    "namespace": "namespace",
    "module": "module",
    "package": "package",
    "class": "class",
    "struct": "struct",
    "derived_type": "derived type",
    "union": "union",
    "enum": "enum",
    "trait": "trait",
    "protocol": "protocol",
    "type_alias": "type alias",
    "concept": "concept",
    "function": "function",
    "subroutine": "subroutine",
    "method": "method",
    "constructor": "constructor",
    "property": "property",
    "attribute": "attribute",
    "variable": "variable",
    "constant": "constant",
    "macro": "macro",
    "deduction_guide": "deduction guide",
}

_KIND_MARKERS = {
    "namespace": "N",
    "module": "M",
    "package": "P",
    "class": "C",
    "struct": "S",
    "derived_type": "T",
    "union": "U",
    "enum": "E",
    "trait": "T",
    "protocol": "P",
    "function": "F",
    "subroutine": "F",
    "method": "F",
    "constructor": "F",
    "type_alias": "T",
    "variable": "V",
    "attribute": "A",
    "property": "P",
    "constant": "C",
    "macro": "D",
    "concept": "K",
    "deduction_guide": "G",
}


def rendering_for(language: str) -> LanguageRendering:
    """Return rendering semantics for one programming language."""

    try:
        return _RENDERINGS[language]
    except KeyError as error:
        raise ValueError(f"unsupported API language: {language}") from error


def language_label(language: str) -> str:
    return _LANGUAGE_LABELS.get(language, language)


def kind_label(kind: str, language: str | None = None) -> str:
    if language in _RENDERINGS:
        specific = _RENDERINGS[language].kind_labels.get(kind)
        if specific is not None:
            return specific
    return _KIND_LABELS.get(kind, kind.replace("_", " "))


def kind_marker(kind: str, language: str | None = None) -> str:
    if language in _RENDERINGS:
        specific = _RENDERINGS[language].kind_markers.get(kind)
        if specific is not None:
            return specific
    return _KIND_MARKERS.get(kind, "·")


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
    "LanguageRendering",
    "kind_label",
    "kind_marker",
    "language_label",
    "rendering_for",
    "source_language",
]
