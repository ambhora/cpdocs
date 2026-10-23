# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Fortran presentation rules."""

from __future__ import annotations

from ...model import ApiEntity, ApiSignature
from ..base import LanguageRendering, parameter_spelling
from .entities import ENTITY_KINDS


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


RENDERING = LanguageRendering(
    separator="::",
    kinds=ENTITY_KINDS,
    source_suffixes=frozenset({".f", ".for", ".ftn", ".f77", ".f90", ".f95", ".f03", ".f08", ".f18"}),
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
)
