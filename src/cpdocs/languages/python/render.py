# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Python presentation rules."""

from __future__ import annotations

from ...model import ApiEntity, ApiSignature
from ..base import LanguageRendering, assigned_property, typed_property


def _parameters(signature: ApiSignature) -> str:
    values: list[str] = []
    parameters = list(signature.parameters)
    positional_only = [item for item in parameters if item.kind == "positional-only"]
    has_var_positional = any(item.kind == "var-positional" for item in parameters)
    keyword_marker_emitted = False
    for index, parameter in enumerate(parameters):
        if (
            parameter.kind == "keyword-only"
            and not has_var_positional
            and not keyword_marker_emitted
        ):
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


def entity_declaration(entity: ApiEntity) -> str:
    if entity.kind in {"class", "protocol"}:
        bases = f"({', '.join(entity.bases)})" if entity.bases else ""
        return f"class {entity.qualified_name}{bases}"
    if entity.kind in {"module", "package"}:
        return f"module {entity.qualified_name}"
    if entity.kind == "type_alias":
        return f"{entity.qualified_name} = {assigned_property(entity)}".rstrip()
    if entity.kind in {"attribute", "variable", "constant", "property"}:
        type_name = typed_property(entity, ignored=frozenset({"property"}))
        assigned = assigned_property(entity)
        value = entity.qualified_name + (f": {type_name}" if type_name else "")
        return value + (f" = {assigned}" if assigned else "")
    return entity.qualified_name


def signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    if signature.spelling:
        return signature.spelling
    prefix = "async def" if "async" in signature.qualifiers else "def"
    value = f"{prefix} {entity.qualified_name}({_parameters(signature)})"
    if signature.returns:
        value += f" -> {signature.returns}"
    return value


def member_summary(entity: ApiEntity) -> str:
    if entity.kind in {"attribute", "variable", "constant", "property"}:
        type_name = typed_property(entity, ignored=frozenset({"property"}))
        assigned = assigned_property(entity)
        value = entity.name + (f": {type_name}" if type_name else "")
        return value + (f" = {assigned}" if assigned else "")
    if entity.kind == "type_alias":
        return f"{entity.name} = {assigned_property(entity)}".rstrip()
    if entity.kind in {"class", "protocol"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


def member_group(entity: ApiEntity) -> str | None:
    if entity.kind in {"class", "protocol", "type_alias"}:
        return "Public Types"
    if entity.kind in {"function", "method", "constructor"}:
        return "Public Functions"
    if entity.kind in {"property", "attribute", "variable", "constant"}:
        return "Public Members"
    return None


RENDERING = LanguageRendering(
    separator=".",
    container_kinds=frozenset({"module", "package"}),
    class_like_kinds=frozenset({"class", "protocol"}),
    type_page_kinds=frozenset({"class", "protocol"}),
    type_like_kinds=frozenset({"class", "protocol", "type_alias"}),
    function_kinds=frozenset({"function", "method", "constructor"}),
    member_value_kinds=frozenset({"property", "attribute", "variable", "constant"}),
    source_suffixes=frozenset({".py", ".pyi"}),
    kind_markers={
        "module": "M",
        "package": "P",
        "class": "C",
        "protocol": "P",
        "function": "F",
        "method": "F",
        "constructor": "F",
        "type_alias": "T",
        "variable": "V",
        "attribute": "A",
        "property": "P",
        "constant": "C",
    },
    kind_labels={"type_alias": "type alias"},
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
    member_group=member_group,
)
