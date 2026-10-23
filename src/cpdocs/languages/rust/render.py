# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Rust presentation rules."""

from __future__ import annotations

import cpdocs.languages.base
import cpdocs.languages.rust.entities
import cpdocs.model


def entity_declaration(entity: cpdocs.model.ApiEntity) -> str:
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


def signature_spelling(entity: cpdocs.model.ApiEntity, signature: cpdocs.model.ApiSignature) -> str:
    if signature.spelling:
        return signature.spelling
    modifiers = [value for value in entity.properties if value != "pub"]
    visibility = "pub " if "pub" in entity.properties else ""
    modifier_prefix = (" ".join(modifiers) + " ") if modifiers else ""
    value = f"{visibility}{modifier_prefix}fn {entity.qualified_name}({cpdocs.languages.base.parameter_spelling(signature)})"
    if signature.returns:
        value += f" -> {signature.returns}"
    return value


def member_summary(entity: cpdocs.model.ApiEntity) -> str:
    if entity.kind in {"struct", "enum", "trait"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


RENDERING = cpdocs.languages.base.LanguageRendering(
    separator="::",
    kinds=cpdocs.languages.rust.entities.ENTITY_KINDS,
    source_suffixes=frozenset({".rs"}),
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
)
