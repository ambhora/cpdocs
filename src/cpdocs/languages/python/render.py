# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Python presentation rules."""

from __future__ import annotations

import cpdocs.languages.base
import cpdocs.languages.python.entities
import cpdocs.model


def _parameters(signature: cpdocs.model.ApiSignature) -> str:
    values: list[str] = []
    parameters = list(signature.parameters)
    positional_only = [item for item in parameters if item.kind == "positional-only"]
    has_var_positional = any(item.kind == "var-positional" for item in parameters)
    keyword_marker_emitted = False
    for index, parameter in enumerate(parameters):
        if parameter.kind == "keyword-only" and not has_var_positional and not keyword_marker_emitted:
            values.append("*")
            keyword_marker_emitted = True
        prefix = ""
        if parameter.kind == "var-positional":
            prefix = "*"
            keyword_marker_emitted = True
        elif parameter.kind == "var-keyword":
            prefix = "**"
        value = prefix + parameter.name
        if parameter.type:
            value += f": {parameter.type}"
        if parameter.default is not None:
            value += f" = {parameter.default}"
        values.append(value)
        if positional_only and index + 1 == len(positional_only):
            values.append("/")
    return ", ".join(values)


def entity_declaration(entity: cpdocs.model.ApiEntity) -> str:
    if entity.kind in {"class", "protocol"}:
        bases = f"({', '.join(entity.bases)})" if entity.bases else ""
        return f"class {entity.qualified_name}{bases}"
    if entity.kind in {"module", "package"}:
        return f"module {entity.qualified_name}"
    if entity.kind == "type_alias":
        return f"{entity.qualified_name} = {cpdocs.languages.base.assigned_property(entity)}".rstrip()
    if entity.kind in {"attribute", "variable", "constant", "property"}:
        type_name = cpdocs.languages.base.typed_property(entity, ignored=frozenset({"property"}))
        assigned = cpdocs.languages.base.assigned_property(entity)
        value = entity.qualified_name + (f": {type_name}" if type_name else "")
        return value + (f" = {assigned}" if assigned else "")
    return entity.qualified_name


def signature_spelling(entity: cpdocs.model.ApiEntity, signature: cpdocs.model.ApiSignature) -> str:
    if signature.spelling:
        return signature.spelling
    prefix = "async def" if "async" in signature.qualifiers else "def"
    value = f"{prefix} {entity.qualified_name}({_parameters(signature)})"
    if signature.returns:
        value += f" -> {signature.returns}"
    return value


def member_summary(entity: cpdocs.model.ApiEntity) -> str:
    if entity.kind in {"attribute", "variable", "constant", "property"}:
        type_name = cpdocs.languages.base.typed_property(entity, ignored=frozenset({"property"}))
        assigned = cpdocs.languages.base.assigned_property(entity)
        value = entity.name + (f": {type_name}" if type_name else "")
        return value + (f" = {assigned}" if assigned else "")
    if entity.kind == "type_alias":
        return f"{entity.name} = {cpdocs.languages.base.assigned_property(entity)}".rstrip()
    if entity.kind in {"class", "protocol"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


RENDERING = cpdocs.languages.base.LanguageRendering(
    separator=".",
    kinds=cpdocs.languages.python.entities.ENTITY_KINDS,
    source_suffixes=frozenset({".py", ".pyi"}),
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
)
