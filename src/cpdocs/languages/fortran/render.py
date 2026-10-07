# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Fortran presentation rules."""

from __future__ import annotations

from ...model import ApiEntity, ApiSignature
from ..base import LanguageRendering, parameter_spelling


def entity_declaration(entity: ApiEntity) -> str:
    if entity.declaration:
        return entity.declaration
    if entity.kind == "module":
        return f"module {entity.qualified_name}"
    if entity.kind == "derived_type":
        return f"type :: {entity.qualified_name}"
    return entity.qualified_name


def signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    if signature.spelling:
        return signature.spelling
    keyword = "subroutine" if entity.kind == "subroutine" else "function"
    value = f"{keyword} {entity.qualified_name}({parameter_spelling(signature)})"
    if signature.returns and entity.kind != "subroutine":
        value += f" result({signature.returns})"
    return value


def member_summary(entity: ApiEntity) -> str:
    if entity.kind == "derived_type":
        return f"type {entity.name}"
    return entity.name


def member_group(entity: ApiEntity) -> str | None:
    if entity.kind == "derived_type":
        return "Public Types"
    if entity.kind in {"function", "subroutine"}:
        return "Public Functions"
    if entity.kind in {"variable", "attribute", "constant"}:
        return "Public Members"
    return None


RENDERING = LanguageRendering(
    separator="::",
    container_kinds=frozenset({"module"}),
    class_like_kinds=frozenset({"derived_type"}),
    type_page_kinds=frozenset({"derived_type"}),
    type_like_kinds=frozenset({"derived_type"}),
    function_kinds=frozenset({"function", "subroutine"}),
    member_value_kinds=frozenset({"variable", "attribute", "constant"}),
    source_suffixes=frozenset({".f", ".for", ".ftn", ".f77", ".f90", ".f95", ".f03", ".f08", ".f18"}),
    kind_markers={
        "module": "M",
        "derived_type": "T",
        "function": "F",
        "subroutine": "F",
        "variable": "V",
        "attribute": "A",
        "constant": "C",
    },
    kind_labels={"derived_type": "derived type"},
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
    member_group=member_group,
)
