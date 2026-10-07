# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""C-family presentation rules for C, C++, CUDA and HIP."""

from __future__ import annotations

from ...model import ApiEntity, ApiSignature
from ..base import (
    LanguageRendering,
    assigned_property,
    parameter_spelling,
    typed_property,
)


def entity_declaration(entity: ApiEntity) -> str:
    if entity.declaration:
        return entity.declaration
    if entity.kind == "namespace":
        value = f"namespace {entity.qualified_name}"
    elif entity.kind in {"class", "struct", "union"}:
        bases = f" : {', '.join(entity.bases)}" if entity.bases else ""
        value = f"{entity.kind} {entity.qualified_name}{bases}"
    elif entity.kind == "enum":
        scoped = " class" if "scoped" in entity.properties else ""
        value = f"enum{scoped} {entity.qualified_name}"
    elif entity.kind == "type_alias":
        value = f"using {entity.qualified_name} = {assigned_property(entity)}".rstrip()
    elif entity.kind in {"attribute", "variable", "constant"}:
        type_name = typed_property(entity)
        assigned = assigned_property(entity)
        value = f"{type_name} {entity.qualified_name}".strip()
        if assigned:
            value += f" = {assigned}"
    elif entity.kind == "concept":
        value = f"concept {entity.qualified_name}"
    elif entity.kind == "macro" and entity.signatures:
        value = entity.signatures[0].spelling or entity.name
    else:
        value = entity.qualified_name
    return f"{entity.template}\n{value}" if entity.template else value


def signature_spelling(entity: ApiEntity, signature: ApiSignature) -> str:
    attribute_spellings = list(
        dict.fromkeys(attribute.spelling for attribute in signature.attributes if attribute.spelling)
    )
    attribute_prefix = " ".join(attribute_spellings)
    if signature.spelling:
        return f"{attribute_prefix} {signature.spelling}".strip()

    parameters = parameter_spelling(signature)
    prefix_values = [
        value
        for value in entity.properties
        if value in {"inline", "constexpr", "consteval", "static", "virtual"}
    ]
    prefix = (" ".join(prefix_values) + " ") if prefix_values else ""
    result = (signature.returns + " ") if signature.returns else ""
    suffix_values = [value for value in signature.qualifiers if value not in prefix_values]
    suffix = (" " + " ".join(suffix_values)) if suffix_values else ""
    declaration = f"{prefix}{result}{entity.qualified_name}({parameters}){suffix}".strip()
    return f"{attribute_prefix} {declaration}".strip()


def member_summary(entity: ApiEntity) -> str:
    if entity.kind in {"attribute", "variable", "constant"}:
        type_name = typed_property(entity)
        assigned = assigned_property(entity)
        value = f"{type_name} {entity.name}".strip()
        return value + (f" = {assigned}" if assigned else "")
    if entity.kind == "type_alias":
        value = f"using {entity.name} = {assigned_property(entity)}".rstrip()
        return f"{entity.template}\n{value}" if entity.template else value
    if entity.kind in {"class", "struct", "union", "enum"}:
        return f"{entity.kind} {entity.name}"
    return entity.name


def member_group(entity: ApiEntity) -> str | None:
    if entity.kind in {"class", "struct", "union", "enum", "type_alias", "concept"}:
        return "Public Types"
    if entity.kind == "deduction_guide":
        return "Deduction Guides"
    if entity.kind in {"function", "method", "constructor"}:
        return "Public Functions"
    if entity.kind in {"attribute", "variable", "constant"}:
        return "Public Members"
    return None


RENDERING = LanguageRendering(
    separator="::",
    container_kinds=frozenset({"namespace"}),
    class_like_kinds=frozenset({"class", "struct", "union"}),
    type_page_kinds=frozenset({"class", "struct", "union", "enum"}),
    type_like_kinds=frozenset({"class", "struct", "union", "enum", "type_alias", "concept"}),
    function_kinds=frozenset({"function", "method", "constructor", "deduction_guide"}),
    member_value_kinds=frozenset({"attribute", "variable", "constant"}),
    source_suffixes=frozenset(
        {".h", ".hh", ".hpp", ".hxx", ".c", ".cc", ".cpp", ".cxx", ".cu", ".cuh", ".hip"}
    ),
    kind_markers={
        "namespace": "N",
        "class": "C",
        "struct": "S",
        "union": "U",
        "enum": "E",
        "function": "F",
        "method": "F",
        "constructor": "F",
        "type_alias": "T",
        "variable": "V",
        "attribute": "A",
        "constant": "C",
        "macro": "D",
        "concept": "K",
        "deduction_guide": "G",
    },
    kind_labels={"deduction_guide": "deduction guide", "type_alias": "type alias"},
    signature_spelling=signature_spelling,
    entity_declaration=entity_declaration,
    member_summary=member_summary,
    member_group=member_group,
)
