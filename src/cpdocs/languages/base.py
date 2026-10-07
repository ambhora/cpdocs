# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Language-specific presentation contract used by generic renderers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..model import ApiEntity, ApiSignature


@dataclass(frozen=True)
class LanguageRendering:
    """Rendering rules that belong to a programming language, not to HTML."""

    separator: str
    container_kinds: frozenset[str]
    class_like_kinds: frozenset[str]
    type_page_kinds: frozenset[str]
    type_like_kinds: frozenset[str]
    function_kinds: frozenset[str]
    member_value_kinds: frozenset[str]
    source_suffixes: frozenset[str]
    kind_markers: dict[str, str]
    kind_labels: dict[str, str]
    signature_spelling: Callable[[ApiEntity, ApiSignature], str]
    entity_declaration: Callable[[ApiEntity], str]
    member_summary: Callable[[ApiEntity], str]
    member_group: Callable[[ApiEntity], str | None]


def parameter_spelling(signature: ApiSignature) -> str:
    """Render conventional typed parameters used by C-family, Fortran and Rust APIs."""

    values: list[str] = []
    for parameter in signature.parameters:
        value = parameter.type or parameter.name
        if parameter.name and parameter.type:
            value += f" {parameter.name}"
        if parameter.default is not None:
            value += f" = {parameter.default}"
        values.append(value)
    return ", ".join(values)


def assigned_property(entity: ApiEntity) -> str:
    """Return an ``= value`` property without its marker."""

    return next((value[2:] for value in entity.properties if value.startswith("= ")), "")


def typed_property(entity: ApiEntity, *, ignored: frozenset[str] = frozenset()) -> str:
    """Return the first property that represents a type rather than an assignment/flag."""

    return next(
        (
            value
            for value in entity.properties
            if not value.startswith("=") and value not in ignored
        ),
        "",
    )
