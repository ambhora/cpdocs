# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Rust presentation rules."""

from __future__ import annotations

from ...model import ApiEntity, ApiSignature
from ..base import LanguageRendering, parameter_spelling


def entity_declaration(entity: ApiEntity) -> str:
    prefix = "pub " if "pub" in entity.properties else ""
    keyword = {
        "struct": "struct",
        "enum": "enum",
        "trait": "trait",
        "module": "mod",
        "type_alias": "type",
        "constant": "const",
    }.get(entity.kind, entity.kind)
    return f"{prefix}{keyword} {entity.qualified_name}".strip()


def signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    if signature.spelling:
        return signature.spelling
    modifiers = [value for value in entity.properties if value != "pub"]
    visibility = "pub " if "pub" in entity.properties else ""
    modifier_prefix = (" ".join(modifiers) + " ") if modifiers else ""
    value = f"{visibility}{modifier_prefix}fn {entity.qualified_name}({parameter_spelling(signature)})"
    if signature.returns:
        value += f" -> {signature.returns}"
    return value


def member_summary(entity: ApiEntity) -> str:
    if entity.kind in {"struct", "enum", "trait"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


def member_group(entity: ApiEntity) -> str | None:
    if entity.kind in {"struct", "union", "enum", "trait", "type_alias"}:
        return "Public Types"
    if entity.kind in {"function", "method"}:
        return "Public Functions"
    if entity.kind in {"variable", "constant", "attribute"}:
        return "Public Members"
    return None


RENDERING = LanguageRendering(
    separator="::",
    container_kinds=frozenset({"module"}),
    class_like_kinds=frozenset({"struct", "union", "trait"}),
    type_page_kinds=frozenset({"struct", "union", "enum", "trait"}),
    type_like_kinds=frozenset({"struct", "union", "enum", "trait", "type_alias"}),
    function_kinds=frozenset({"function", "method"}),
    member_value_kinds=frozenset({"variable", "constant", "attribute"}),
    source_suffixes=frozenset({".rs"}),
    kind_markers={
        "module": "M",
        "struct": "S",
        "union": "U",
        "enum": "E",
        "trait": "T",
        "function": "F",
        "method": "F",
        "type_alias": "T",
        "variable": "V",
        "attribute": "A",
        "constant": "C",
        "macro": "D",
    },
    kind_labels={"type_alias": "type alias"},
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
    member_group=member_group,
)
