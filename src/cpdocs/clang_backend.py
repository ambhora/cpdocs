# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Clang semantic-AST backend for C and C++ API extraction.

The backend intentionally treats Clang as the semantic authority.  It invokes the compiler frontend
with ``-ast-dump=json`` only as a transport format; the rest of cpdocs consumes the normalized
:class:`ApiGraph`, so this adapter can later be replaced by LibTooling without touching rendering,
versioning, or availability handling.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Iterable
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from .contract import ParseOptions
from .model import (
    ApiAttribute,
    ApiEntity,
    ApiGraph,
    ApiParameter,
    ApiSignature,
    SourceLocation,
    relative_source_path,
    stable_entity_id,
)

_RECORD_KINDS = {
    "CXXRecordDecl": "class",
    "RecordDecl": "struct",
    "ClassTemplateDecl": "class",
    "ClassTemplatePartialSpecializationDecl": "class",
    "ClassTemplateSpecializationDecl": "class",
}
_CALLABLE_KINDS = {
    "FunctionDecl": "function",
    "CXXMethodDecl": "method",
    "CXXConstructorDecl": "constructor",
    "CXXDestructorDecl": "method",
    "ConversionFunctionDecl": "method",
}
_ALIAS_KINDS = {"TypedefDecl": "type_alias", "TypeAliasDecl": "type_alias"}
_VARIABLE_KINDS = {"VarDecl": "variable", "FieldDecl": "attribute"}
_SKIP_NAMES = {"__va_list_tag", "__NSConstantString_tag"}


def _node_file(
    node: dict[str, object],
    inherited: Path | None,
    file_state: list[Path | None],
) -> Path | None:
    """Resolve Clang's state-compressed JSON source location to an explicit file path."""

    loc = node.get("loc")
    if isinstance(loc, dict):
        file_value = loc.get("file")
        if isinstance(file_value, str) and file_value:
            value = Path(file_value)
            file_state[0] = value
            return value
    if inherited is not None:
        return inherited
    return file_state[0]


@lru_cache(maxsize=256)
def _source_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def _line_column_from_offset(path: Path, offset: int) -> tuple[int | None, int | None]:
    content = _source_bytes(path)
    if not content or offset < 0 or offset > len(content):
        return None, None
    before = content[:offset]
    line = before.count(b"\n") + 1
    last_newline = before.rfind(b"\n")
    column = offset + 1 if last_newline < 0 else offset - last_newline
    return line, column


def _inside(path: Path | None, roots: Iterable[Path]) -> bool:
    if path is None:
        return False
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def _logical_public_path(path: Path, public_roots: tuple[Path, ...], project_root: Path) -> str:
    for root in public_roots:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
    return relative_source_path(path, project_root)


def _comment_line(node: dict[str, object]) -> int | None:
    loc = node.get("loc")
    if isinstance(loc, dict) and isinstance(loc.get("line"), int):
        return int(loc["line"])
    return None


def _paragraph_text(node: dict[str, object]) -> str:
    """Rebuild a paragraph from its text and inline HTML pieces.

    Clang splits a paragraph into one text node per source line and parses ``<name>`` as an HTML
    tag even inside backticks; ``labelled<double>`` must come back without added spaces.
    """

    pieces: list[str] = []
    previous_line: int | None = None
    for child in node.get("inner", []) if isinstance(node.get("inner"), list) else []:
        if not isinstance(child, dict):
            continue
        kind = child.get("kind")
        line = _comment_line(child)
        if kind == "TextComment":
            text = str(child.get("text", ""))
            if pieces and line is not None and previous_line is not None and line != previous_line:
                pieces.append(" ")
            pieces.append(text)
        elif kind == "HTMLStartTagComment":
            pieces.append(f"<{child.get('name', '')}" + ("/>" if child.get("selfClosing") else ">"))
        elif kind == "HTMLEndTagComment":
            pieces.append(f"</{child.get('name', '')}>")
        elif kind == "InlineCommandComment":
            arguments = child.get("args")
            if isinstance(arguments, list) and arguments:
                pieces.append("`" + " ".join(str(value) for value in arguments) + "`")
        if line is not None:
            previous_line = line
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def _comment_text(node: dict[str, object]) -> str:
    paragraphs: list[str] = []

    def flatten(current: dict[str, object]) -> str:
        kind = str(current.get("kind", ""))
        if kind == "ParagraphComment":
            return _paragraph_text(current)
        text = current.get("text")
        if isinstance(text, str):
            return text.strip()
        children = current.get("inner")
        parts: list[str] = []
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    value = flatten(child)
                    if value:
                        parts.append(value)
        body = " ".join(parts).strip()
        # Parameter and return commands are kept as canonical ``@tparam``, ``@param`` and
        # ``@return`` paragraphs; the renderer turns them into lists below the description.
        if kind in {"ParamCommandComment", "TParamCommandComment"}:
            parameter = current.get("param") or current.get("paramName")
            command = "tparam" if kind == "TParamCommandComment" else "param"
            if parameter:
                return f"@{command} {parameter} {body}".rstrip()
        if kind == "BlockCommandComment":
            command = current.get("name")
            if command in {"return", "returns", "result"} and body:
                return f"@return {body}"
            if command in {"throw", "throws", "exception"} and body:
                return f"@throws {body}"
        return body

    children = node.get("inner")
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            value = flatten(child)
            if value:
                paragraphs.append(value)
    return "\n\n".join(paragraphs)


def _attached_comment(node: dict[str, object]) -> str:
    children = node.get("inner")
    if not isinstance(children, list):
        return ""
    for child in children:
        if isinstance(child, dict) and child.get("kind") == "FullComment":
            return _comment_text(child)
    return ""


def _location(
    node: dict[str, object],
    path: Path | None,
    project_root: Path,
    public_roots: tuple[Path, ...],
) -> SourceLocation | None:
    if path is None:
        return None
    loc = node.get("loc")
    line = None
    column = None
    if isinstance(loc, dict):
        if isinstance(loc.get("line"), int):
            line = int(loc["line"])
        if isinstance(loc.get("col"), int):
            column = int(loc["col"])
        if (line is None or column is None) and isinstance(loc.get("offset"), int):
            inferred_line, inferred_column = _line_column_from_offset(path, int(loc["offset"]))
            line = line or inferred_line
            column = column or inferred_column
    # Public API locations use the installed/header namespace where possible. Generated headers
    # therefore do not leak profile-specific build-directory paths into the published reference.
    return SourceLocation(_logical_public_path(path, public_roots, project_root), line, column)


def _related_markers(node: dict[str, object], path: Path | None) -> list[str]:
    """Read CPDOCS-API-RELATES-TO markers immediately preceding a declaration.

    These markers are intentionally ordinary source comments rather than part of the Doxygen-style
    documentation block.  Clang therefore does not consistently include them in FullComment nodes,
    even with ``-fparse-all-comments``.  Source locations are semantic, so using them to recover the
    adjacent marker is deterministic and keeps this small cpdocs extension independent of Doxygen.
    """

    if path is None:
        return []
    loc = node.get("loc")
    line: int | None = None
    if isinstance(loc, dict):
        if isinstance(loc.get("line"), int):
            line = int(loc["line"])
        elif isinstance(loc.get("offset"), int):
            line, _ = _line_column_from_offset(path, int(loc["offset"]))
    if line is None or line <= 1:
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    marker = re.compile(r"CPDOCS-API-RELATES-TO:\s*(.+?)\s*(?:\*/)?$")
    # The marker is conventionally the comment directly above the declaration.  Permit a small
    # comment/blank window so attributes do not make the convention brittle, but stop at source.
    values: list[str] = []
    for index in range(line - 2, max(-1, line - 12), -1):
        text = lines[index].strip()
        match = marker.search(text)
        if match:
            for value in re.split(r"\s*,\s*", match.group(1)):
                if value and value not in values:
                    values.append(value)
            continue
        if not text:
            continue
        if text.startswith(("//", "/*", "*", "*/", "[[")):
            continue
        break
    return values


def _qual_type(node: dict[str, object]) -> str:
    value = node.get("type")
    if isinstance(value, dict):
        spelling = value.get("qualType")
        if isinstance(spelling, str):
            return spelling
    return ""


def _parameters(node: dict[str, object]) -> tuple[ApiParameter, ...]:
    parameters: list[ApiParameter] = []
    children = node.get("inner")
    if not isinstance(children, list):
        return ()
    for child in children:
        if not isinstance(child, dict) or child.get("kind") != "ParmVarDecl":
            continue
        parameters.append(
            ApiParameter(
                name=str(child.get("name", "")),
                type=_qual_type(child),
            )
        )
    return tuple(parameters)


def _return_type(node: dict[str, object]) -> str:
    """Return type from Clang's function type spelling ``RET (PARAMS) QUALIFIERS``."""

    kind = str(node.get("kind", ""))
    if kind in {"CXXConstructorDecl", "CXXDestructorDecl", "CXXConversionDecl"}:
        return ""
    spelling = _qual_type(node)
    depth = 0
    for index, character in enumerate(spelling):
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif character == "(" and depth == 0:
            result = spelling[:index].strip()
            trailing = re.search(r"\)\s*(?:[a-z&\s]*)->\s*(.+)$", spelling[index:])
            if result == "auto" and trailing:
                return trailing.group(1).strip()
            return result
    return ""


def _qualifiers(node: dict[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    for field, label in (
        ("inline", "inline"),
        ("constexpr", "constexpr"),
        ("consteval", "consteval"),
        ("virtual", "virtual"),
        ("pure", "pure virtual"),
    ):
        if node.get(field) is True:
            values.append(label)
    storage = node.get("storageClass")
    if isinstance(storage, str) and storage:
        values.append(storage)
    spelling = _qual_type(node)
    suffix = spelling.rsplit(")", 1)[1] if ")" in spelling else ""
    for token in ("const", "volatile", "noexcept"):
        if re.search(rf"\b{token}\b", suffix) and token not in values:
            values.append(token)
    if "&&" in suffix:
        values.append("&&")
    elif "&" in suffix:
        values.append("&")
    return tuple(values)


_ATTRIBUTE_NAMES = {
    "WarnUnusedResultAttr": "nodiscard",
    "DeprecatedAttr": "deprecated",
    "UnusedAttr": "maybe_unused",
    "CXX11NoReturnAttr": "noreturn",
    "NoUniqueAddressAttr": "no_unique_address",
    "CarriesDependencyAttr": "carries_dependency",
    "LikelyAttr": "likely",
    "UnlikelyAttr": "unlikely",
}


def _attribute_name(node: dict[str, object]) -> str:
    kind = str(node.get("kind", ""))
    if kind in _ATTRIBUTE_NAMES:
        return _ATTRIBUTE_NAMES[kind]
    if not kind.endswith("Attr"):
        return ""
    stem = kind[:-4]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", stem).lower()


def _attribute_spelling(node: dict[str, object], path: Path | None) -> str:
    """Recover the complete ``[[...]]`` specifier containing one Clang Attr node."""

    if path is None:
        return ""
    offsets = _range_offsets(node)
    if offsets is None:
        return ""
    data = _SOURCE_BYTES.get(path)
    if data is None:
        try:
            data = path.read_bytes()
        except OSError:
            return ""
        _SOURCE_BYTES[path] = data
    start, stop = offsets
    left = data.rfind(b"[[", max(0, start - 2048), start + 1)
    if left < 0:
        return ""
    right = data.find(b"]]", left + 2, min(len(data), stop + 2048))
    if right < 0 or not (left <= start and stop <= right + 2):
        return ""
    return re.sub(r"\s+", " ", data[left : right + 2].decode("utf-8", errors="replace")).strip()


def _attributes(node: dict[str, object], path: Path | None) -> tuple[ApiAttribute, ...]:
    children = node.get("inner")
    if not isinstance(children, list):
        return ()
    values: list[ApiAttribute] = []
    for child in children:
        if not isinstance(child, dict) or not str(child.get("kind", "")).endswith("Attr"):
            continue
        name = _attribute_name(child)
        if not name:
            continue
        attribute = ApiAttribute(name=name, spelling=_attribute_spelling(child, path))
        if attribute not in values:
            values.append(attribute)
    return tuple(values)


def _signature(node: dict[str, object], path: Path | None) -> ApiSignature:
    parameters = _parameters(node)
    qualifiers = _qualifiers(node)
    return ApiSignature(
        parameters=parameters,
        returns=_return_type(node),
        qualifiers=qualifiers,
        attributes=_attributes(node, path),
    )


# --------------------------------------------------------------------------------------------------
# Source text of declarations
#
# Clang's JSON dump keeps template parameter lists, requires-clauses and concept definitions only as
# expression trees. What a reader needs is the declaration as written, so these helpers slice it out
# of the header using the byte offsets of the AST node ranges.
# --------------------------------------------------------------------------------------------------

_SOURCE_BYTES: dict[Path, bytes] = {}
_TEMPLATE_KINDS = {
    "ClassTemplateDecl",
    "FunctionTemplateDecl",
    "VarTemplateDecl",
    "TypeAliasTemplateDecl",
}
_TEMPLATE_PARAMETER_KINDS = {
    "TemplateTypeParmDecl",
    "NonTypeTemplateParmDecl",
    "TemplateTemplateParmDecl",
}
_SPECIALIZATION_KINDS = {
    "ClassTemplateSpecializationDecl",
    "ClassTemplatePartialSpecializationDecl",
}


def _offset(location: object) -> int | None:
    if not isinstance(location, dict):
        return None
    value = location.get("offset")
    if isinstance(value, int):
        return value
    return None


def _range_offsets(node: dict[str, object]) -> tuple[int, int] | None:
    source_range = node.get("range")
    if not isinstance(source_range, dict):
        return None
    begin = source_range.get("begin")
    end = source_range.get("end")
    start = _offset(begin)
    stop = _offset(end)
    if start is None or stop is None or not isinstance(end, dict):
        return None
    token = end.get("tokLen")
    return start, stop + (token if isinstance(token, int) else 0)


def _source_slice(path: Path | None, start: int, stop: int) -> str:
    if path is None:
        return ""
    data = _SOURCE_BYTES.get(path)
    if data is None:
        try:
            data = path.read_bytes()
        except OSError:
            data = b""
        _SOURCE_BYTES[path] = data
    return data[start:stop].decode("utf-8", errors="replace")


def _normalize_declaration(text: str) -> str:
    """Collapse whitespace inside a declaration while keeping its line structure readable."""

    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    indents = [len(line) - len(line.lstrip()) for line in lines[1:]]
    common = min(indents) if indents else 0
    result = [re.sub(r"\s+", " ", lines[0]).strip()]
    for line in lines[1:]:
        body = line[common:]
        indent = len(body) - len(body.lstrip())
        result.append(" " * indent + re.sub(r"\s+", " ", body.strip()))
    return "\n".join(result).rstrip(";").rstrip()


def _templated_child(node: dict[str, object]) -> dict[str, object] | None:
    children = node.get("inner")
    if not isinstance(children, list):
        return None
    for child in children:
        if (
            isinstance(child, dict)
            and child.get("kind") not in _TEMPLATE_PARAMETER_KINDS
            and not child.get("isImplicit")
            and _range_offsets(child) is not None
            and str(child.get("kind", "")).endswith("Decl")
        ):
            return child
    return None


def _template_header(node: dict[str, object], child: dict[str, object], path: Path | None) -> str:
    """``template <...>`` and any leading requires-clause, as written before ``child``."""

    outer = _range_offsets(node)
    inner = _range_offsets(child)
    if outer is None or inner is None or inner[0] <= outer[0]:
        return ""
    return _normalize_declaration(_source_slice(path, outer[0], inner[0]))


def _specialization(node: dict[str, object], path: Path | None) -> tuple[str, str] | None:
    """Template header and argument list of an explicit or partial specialization."""

    whole = _range_offsets(node)
    if whole is None:
        return None
    text = _source_slice(path, whole[0], whole[1])
    name = str(node.get("name", ""))
    match = re.search(r"\b(?:struct|class|union)\s+" + re.escape(name) + r"\s*<", text)
    if match is None:
        return None
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "<":
            depth += 1
        elif text[index] == ">":
            depth -= 1
            if depth == 0:
                arguments = re.sub(r"\s+", " ", text[match.end() - 1 : index + 1])
                return _normalize_declaration(text[: match.start()]), arguments
    return None


def _initializer(node: dict[str, object], path: Path | None) -> str:
    """The written initializer of a variable declaration, if it has one."""

    if node.get("init") is None:
        return ""
    whole = _range_offsets(node)
    if whole is None:
        return ""
    text = _source_slice(path, whole[0], whole[1])
    name = str(node.get("name", ""))
    match = re.search(r"\b" + re.escape(name) + r"\s*(=|\{)", text)
    if match is None:
        return ""
    value = text[match.end() :] if match.group(1) == "=" else "{" + text[match.end() :]
    return re.sub(r"\s+", " ", value).strip().rstrip(";").strip()


def _is_tag_typedef(
    node: dict[str, object], name: str, scopes: tuple[str, ...], graph: ApiGraph
) -> bool:
    """Whether a typedef merely re-exports the record or enum tag of the same name.

    The typedef's documentation is moved onto the tag when the tag has none.
    """

    target = _qual_type(node)
    if target not in {f"struct {name}", f"union {name}", f"enum {name}", f"class {name}"}:
        return False
    qualified = "::".join((*scopes, name))
    for tag_kind in ("struct", "union", "enum", "class"):
        tag = graph.entities.get(stable_entity_id("cpp", tag_kind, qualified))
        if tag is not None:
            if not tag.documentation:
                tag.documentation = _attached_comment(node)
            return True
    return False


def _record_kind(node: dict[str, object]) -> str:
    tag = node.get("tagUsed")
    if isinstance(tag, str) and tag in {"class", "struct", "union"}:
        return tag
    return _RECORD_KINDS.get(str(node.get("kind", "")), "class")


def _entity_properties(node: dict[str, object]) -> list[str]:
    properties = list(_qualifiers(node))
    access = node.get("access")
    if isinstance(access, str) and access not in {"", "public"}:
        properties.append(access)
    if node.get("isAggregate") is True:
        properties.append("aggregate")
    return list(dict.fromkeys(properties))


def _base_names(node: dict[str, object]) -> list[str]:
    values: list[str] = []
    bases = node.get("bases")
    if isinstance(bases, list):
        for base in bases:
            if not isinstance(base, dict):
                continue
            spelling = _qual_type(base)
            if spelling and spelling not in values:
                values.append(spelling)
    return values


def _walk_ast(
    node: dict[str, object],
    *,
    graph: ApiGraph,
    project_root: Path,
    public_roots: tuple[Path, ...],
    inherited_file: Path | None = None,
    parent_entity: ApiEntity | None = None,
    scopes: tuple[str, ...] = (),
    template_context: bool = False,
    access: str = "public",
    file_state: list[Path | None] | None = None,
) -> None:
    if file_state is None:
        file_state = [inherited_file]
    kind = str(node.get("kind", ""))
    path = _node_file(node, inherited_file, file_state)
    name = str(node.get("name", ""))
    in_public_file = _inside(path, public_roots)

    if node.get("isImplicit") is True:
        return
    if name in _SKIP_NAMES:
        return

    # Clang represents C++ access changes as ordered AccessSpecDecl siblings rather than copying the
    # access level onto every member. The parent traversal supplies the effective access here.
    if access != "public" and kind in {
        *_RECORD_KINDS,
        *_CALLABLE_KINDS,
        *_ALIAS_KINDS,
        *_VARIABLE_KINDS,
        "EnumDecl",
        "ConceptDecl",
        "FunctionTemplateDecl",
    }:
        return

    # Implicit instantiations carry no source range; only written specializations are API.
    if kind in _SPECIALIZATION_KINDS and _range_offsets(node) is None:
        return
    if kind in _TEMPLATE_KINDS:
        templated = _templated_child(node)
        if templated is not None:
            templated["__cpdocs_template"] = _template_header(node, templated, path)
            if templated.get("kind") == "CXXDeductionGuideDecl":
                templated["__cpdocs_guide"] = _normalize_declaration(
                    _source_slice(path, *(_range_offsets(node) or (0, 0)))
                )
    template_header = str(node.get("__cpdocs_template", ""))

    entity: ApiEntity | None = None
    next_scopes = scopes
    next_parent = parent_entity
    next_template = template_context or kind in {"FunctionTemplateDecl", "ClassTemplateDecl"}

    if kind == "NamespaceDecl" and name and in_public_file:
        qualified = "::".join((*scopes, name))
        entity = ApiEntity(
            id=stable_entity_id("cpp", "namespace", qualified),
            language="cpp",
            kind="namespace",
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            related=_related_markers(node, path),
        )
        graph.add(entity)
        entity = graph.entities[entity.id]
        next_scopes = (*scopes, name)
        next_parent = entity

    elif kind in _RECORD_KINDS and name and in_public_file:
        # ClassTemplateDecl wraps the actual CXXRecordDecl.  Let the record child own the semantic
        # entity, but propagate template context so it receives a template property.
        if kind == "ClassTemplateDecl":
            pass
        else:
            display_name = name
            if kind in _SPECIALIZATION_KINDS:
                specialization = _specialization(node, path)
                if specialization is not None:
                    template_header, arguments = specialization
                    display_name = name + arguments
            qualified = "::".join((*scopes, display_name))
            record_kind = _record_kind(node)
            entity = ApiEntity(
                id=stable_entity_id("cpp", record_kind, qualified),
                language="cpp",
                kind=record_kind,
                name=display_name,
                template=template_header,
                qualified_name=qualified,
                parent=parent_entity.id if parent_entity else None,
                documentation=_attached_comment(node),
                source=_location(node, path, project_root, public_roots),
                properties=_entity_properties(node)
                + (["template"] if template_context or template_header else []),
                bases=_base_names(node),
                related=_related_markers(node, path),
            )
            graph.add(entity)
            entity = graph.entities[entity.id]
            next_scopes = (*scopes, display_name)
            next_parent = entity

    elif kind == "CXXDeductionGuideDecl" and in_public_file:
        # A deduction guide belongs to the class template it deduces.
        guided = name.removeprefix("<deduction guide for ").removesuffix(">")
        record_name = "::".join((*scopes, guided))
        owner = next(
            (
                graph.entities[stable_entity_id("cpp", record_kind, record_name)]
                for record_kind in ("struct", "class", "union")
                if stable_entity_id("cpp", record_kind, record_name) in graph.entities
            ),
            None,
        )
        spelling = str(node.get("__cpdocs_guide", "")) or _normalize_declaration(
            _source_slice(path, *(_range_offsets(node) or (0, 0)))
        )
        if owner is not None and spelling:
            qualified = f"{record_name}::{guided}"
            guide = ApiEntity(
                id=stable_entity_id("cpp", "deduction_guide", qualified),
                language="cpp",
                kind="deduction_guide",
                name=guided,
                qualified_name=qualified,
                parent=owner.id,
                signatures=[ApiSignature(spelling=spelling)],
                documentation=_attached_comment(node),
                source=_location(node, path, project_root, public_roots),
            )
            graph.add(guide)
        return

    elif kind in _CALLABLE_KINDS and name and in_public_file:
        qualified = "::".join((*scopes, name))
        callable_kind = _CALLABLE_KINDS[kind]
        entity_id = stable_entity_id("cpp", callable_kind, qualified)
        entity = ApiEntity(
            id=entity_id,
            language="cpp",
            kind=callable_kind,
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            signatures=[
                replace(
                    _signature(node, path),
                    template=template_header,
                    documentation=_attached_comment(node),
                    source=_location(node, path, project_root, public_roots),
                )
            ],
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            properties=_entity_properties(node)
            + (["template"] if template_context or template_header else []),
            related=_related_markers(node, path),
        )
        graph.add(entity)
        next_parent = graph.entities[entity_id]

    elif kind == "EnumDecl" and name and in_public_file:
        qualified = "::".join((*scopes, name))
        entity = ApiEntity(
            id=stable_entity_id("cpp", "enum", qualified),
            language="cpp",
            kind="enum",
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            properties=["scoped"] if node.get("scopedEnumTag") else [],
            related=_related_markers(node, path),
        )
        graph.add(entity)
        entity = graph.entities[entity.id]
        next_scopes = (*scopes, name)
        next_parent = entity

    elif kind == "EnumConstantDecl" and name and in_public_file:
        qualified = "::".join((*scopes, name))
        entity = ApiEntity(
            id=stable_entity_id("cpp", "constant", qualified),
            language="cpp",
            kind="constant",
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            related=_related_markers(node, path),
        )
        graph.add(entity)

    elif (
        kind in _ALIAS_KINDS
        and name
        and in_public_file
        and _is_tag_typedef(node, name, scopes, graph)
    ):
        # ``typedef struct ring {...} ring;`` names the tag a second time; document the tag only.
        pass

    elif kind in _ALIAS_KINDS and name and in_public_file:
        qualified = "::".join((*scopes, name))
        target = _qual_type(node)
        entity = ApiEntity(
            id=stable_entity_id("cpp", "type_alias", qualified),
            language="cpp",
            kind="type_alias",
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            properties=[f"= {target}"] if target else [],
            related=_related_markers(node, path),
            template=template_header,
        )
        graph.add(entity)

    elif kind in _VARIABLE_KINDS and name and in_public_file:
        qualified = "::".join((*scopes, name))
        variable_kind = _VARIABLE_KINDS[kind]
        entity = ApiEntity(
            id=stable_entity_id("cpp", variable_kind, qualified),
            language="cpp",
            kind=variable_kind,
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            properties=([_qual_type(node)] if _qual_type(node) else [])
            + ([f"= {_initializer(node, path)}"] if _initializer(node, path) else []),
            related=_related_markers(node, path),
            template=template_header,
        )
        graph.add(entity)

    elif kind == "ConceptDecl" and name and in_public_file:
        qualified = "::".join((*scopes, name))
        entity = ApiEntity(
            id=stable_entity_id("cpp", "concept", qualified),
            language="cpp",
            kind="concept",
            name=name,
            qualified_name=qualified,
            parent=parent_entity.id if parent_entity else None,
            declaration=_normalize_declaration(
                _source_slice(path, *(_range_offsets(node) or (0, 0)))
            ),
            documentation=_attached_comment(node),
            source=_location(node, path, project_root, public_roots),
            related=_related_markers(node, path),
        )
        graph.add(entity)

    # Callable bodies, variable initializers, aliases, and concepts can contain declarations that are
    # implementation details. Their semantic metadata has already been harvested above; only
    # namespace/record/enum/template containers should contribute nested public API entities.
    if kind in {
        *_CALLABLE_KINDS,
        *_ALIAS_KINDS,
        *_VARIABLE_KINDS,
        "ConceptDecl",
        "EnumConstantDecl",
    }:
        return

    children = node.get("inner")
    if not isinstance(children, list):
        return

    # Comments and parameter declarations are metadata, not API entities. For records, preserve the
    # source-order access state because Clang emits AccessSpecDecl markers as siblings.
    member_access = access
    if entity is not None and entity.kind in {"class", "struct", "union"}:
        member_access = "private" if entity.kind == "class" else "public"
    for child in children:
        if not isinstance(child, dict):
            continue
        child_kind = child.get("kind")
        if child_kind == "AccessSpecDecl":
            child_access = child.get("access")
            if isinstance(child_access, str) and child_access:
                member_access = child_access
            continue
        if child_kind in {
            "FullComment",
            "ParagraphComment",
            "TextComment",
            "ParmVarDecl",
            "CXXBaseSpecifier",
        }:
            continue
        _walk_ast(
            child,
            graph=graph,
            project_root=project_root,
            public_roots=public_roots,
            inherited_file=path,
            parent_entity=next_parent,
            scopes=next_scopes,
            template_context=next_template,
            access=member_access,
            file_state=file_state,
        )


def _compile_entry_arguments(entry: dict[str, object]) -> list[str]:
    arguments = entry.get("arguments")
    if isinstance(arguments, list) and all(isinstance(value, str) for value in arguments):
        return list(arguments)
    command = entry.get("command")
    if isinstance(command, str):
        return shlex.split(command)
    return []


def _choose_compile_entry(
    entries: list[dict[str, object]], *, language: str
) -> dict[str, object] | None:
    preferred = {".c"} if language == "c" else {".cc", ".cpp", ".cxx", ".c++", ".C"}
    for entry in entries:
        source = entry.get("file")
        if isinstance(source, str) and Path(source).suffix in preferred:
            return entry
    return entries[0] if entries else None


def _frontend_arguments(
    entry: dict[str, object] | None,
    *,
    public_roots: tuple[Path, ...],
    predefines: Iterable[str],
) -> tuple[Path | None, list[str]]:
    if entry is None:
        args = ["-std=c++20"]
        directory = None
    else:
        raw = _compile_entry_arguments(entry)
        directory_value = entry.get("directory")
        directory = Path(directory_value) if isinstance(directory_value, str) else None
        args = raw[1:] if raw else []

        source = entry.get("file")
        source_values = {str(source)} if isinstance(source, str) else set()
        if isinstance(source, str) and directory is not None:
            source_values.add(str((directory / source).resolve()))

        cleaned: list[str] = []
        skip_next = False
        options_with_value = {"-o", "-MF", "-MT", "-MQ", "--serialize-diagnostics"}
        for argument in args:
            if skip_next:
                skip_next = False
                continue
            if argument in options_with_value:
                skip_next = True
                continue
            if argument in {"-c", "-MD", "-MMD", "-MP"}:
                continue
            if argument in source_values:
                continue
            try:
                if source_values and str(Path(argument).resolve()) in source_values:
                    continue
            except OSError:
                pass
            if argument.startswith("-o") and len(argument) > 2:
                continue
            cleaned.append(argument)
        args = cleaned

    for root in public_roots:
        args.append(f"-I{root}")
    names: set[str] = set()
    for value in predefines:
        if not value:
            continue
        args.append(f"-D{value}")
        names.add(value.split("=", 1)[0])
    if "__CUDACC__" in names or "__HIPCC__" in names:
        args.extend(["-D__host__=", "-D__device__=", "-D__global__="])
    return directory, args


def _public_headers(public_roots: Iterable[Path]) -> list[Path]:
    suffixes = {".h", ".hh", ".hpp", ".hxx", ".cuh"}
    values: set[Path] = set()
    for root in public_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                values.add(path.resolve())
    return sorted(values)


def _write_umbrella(path: Path, headers: Iterable[Path]) -> None:
    lines = ["// Generated by cpdocs for semantic API extraction."]
    for header in headers:
        escaped = header.as_posix().replace('"', '\\"')
        lines.append(f'#include "{escaped}"')
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _include_guard_name(lines: list[str]) -> str | None:
    """Recognize the conventional #ifndef/#define include-guard pair near the file start."""

    ifndef = re.compile(r"^\s*#\s*ifndef\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
    define = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b")
    candidate: str | None = None
    for line in lines[:40]:
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
        ):
            continue
        if candidate is None:
            match = ifndef.match(line)
            if match is None:
                if stripped.startswith("#pragma once"):
                    return None
                continue
            candidate = match.group(1)
            continue
        match = define.match(line)
        if match is not None:
            return candidate if match.group(1) == candidate else None
        if not stripped.startswith("#"):
            return None
    return None


def _macro_candidates(
    headers: Iterable[Path],
    project_root: Path,
    public_roots: tuple[Path, ...],
    active_definitions: dict[str, str],
) -> list[ApiEntity]:
    entities: list[ApiEntity] = []
    define = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)(\([^\n]*?\))?(?:\s+(.*))?$")
    comment_lines: list[str] = []
    for header in headers:
        try:
            lines = header.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        include_guard = _include_guard_name(lines)
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("///"):
                comment_lines.append(stripped[3:].strip())
                continue
            match = define.match(line)
            if match:
                name = match.group(1)
                if name == include_guard:
                    comment_lines.clear()
                    continue
                args = match.group(2) or ""
                value = (match.group(3) or "").strip()
                candidate_tail = " ".join((args + ((" " + value) if value else "")).split())
                active_tail = active_definitions.get(name)
                if active_tail is None or candidate_tail != active_tail:
                    comment_lines.clear()
                    continue
                parameters: tuple[ApiParameter, ...] = ()
                if args:
                    names = [item.strip() for item in args[1:-1].split(",") if item.strip()]
                    parameters = tuple(ApiParameter(item) for item in names)
                entity = ApiEntity(
                    id=stable_entity_id("cpp", "macro", name),
                    language="cpp",
                    kind="macro",
                    name=name,
                    qualified_name=name,
                    signatures=[ApiSignature(parameters=parameters, spelling=line.strip())],
                    documentation=" ".join(comment_lines).strip(),
                    source=SourceLocation(
                        _logical_public_path(header, public_roots, project_root), number, 1
                    ),
                    properties=[value] if value else [],
                )
                entities.append(entity)
                comment_lines.clear()
                continue
            if stripped and not stripped.startswith("//"):
                comment_lines.clear()
    return entities


def _active_macro_definitions(
    *,
    clang_executable: str,
    frontend_args: list[str],
    umbrella: Path,
    cwd: Path,
) -> dict[str, str]:
    """Return macro definitions active under the exact semantic extraction configuration."""

    result = subprocess.run(
        [clang_executable, *frontend_args, "-dM", "-E", str(umbrella)],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError("Clang preprocessor macro discovery failed:\n" + result.stderr.strip())
    pattern = re.compile(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)(.*)$")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match is not None:
            values[match.group(1)] = " ".join(match.group(2).strip().split())
    return values


def _parse_arguments(
    parse: ParseOptions, *, language: str, api_roots: tuple[Path, ...]
) -> tuple[Path | None, list[str]]:
    """Assemble the Clang frontend arguments described by one feature-set manifest.

    A compilation database, when the build system provides one, contributes the options of one
    representative translation unit. The explicit manifest fields are appended afterwards so that
    they take precedence.
    """

    directory: Path | None = None
    args: list[str] = []
    if parse.compile_database is not None:
        try:
            raw_entries = json.loads(parse.compile_database.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Cannot read compilation database {parse.compile_database}: {error}"
            ) from error
        entries = (
            [entry for entry in raw_entries if isinstance(entry, dict)]
            if isinstance(raw_entries, list)
            else []
        )
        entry = _choose_compile_entry(entries, language=language)
        if entry is not None:
            directory, args = _frontend_arguments(entry, public_roots=(), predefines=())

    args.extend(["-x", "c" if language == "c" else "c++"])
    if parse.standard:
        args.append(f"-std={parse.standard}")
    for path in parse.include:
        args.append(f"-I{path}")
    for root in api_roots:
        args.append(f"-I{root}")
    for path in parse.system_include:
        args.extend(["-isystem", str(path)])
    names: set[str] = set()
    for value in parse.define:
        if value:
            args.append(f"-D{value}")
            names.add(value.split("=", 1)[0])
    if "__CUDACC__" in names or "__HIPCC__" in names:
        args.extend(["-D__host__=", "-D__device__=", "-D__global__="])
    args.extend(parse.flags)
    return directory, args


def _relabel(graph: ApiGraph, language: str) -> None:
    """Apply the semantic API language after extraction through the shared C/C++ walker.

    Namespace nodes are language-neutral containers in the rendered hierarchy.  Keeping their C++
    identity lets C++, CUDA and HIP definitions share one namespace tree while the concrete API
    definitions remain distinct by semantic language.
    """

    if language == "cpp":
        return

    entities = list(graph.entities.values())
    identifiers: dict[str, str] = {}
    for entity in entities:
        if entity.language == "cpp" and entity.kind != "namespace":
            identifiers[entity.id] = language + entity.id[3:]
        else:
            identifiers[entity.id] = entity.id

    graph.entities.clear()
    for entity in entities:
        entity.id = identifiers.get(entity.id, entity.id)
        if entity.parent is not None:
            entity.parent = identifiers.get(entity.parent, entity.parent)
        if entity.kind != "namespace":
            entity.language = language
        graph.entities[entity.id] = entity
    graph.language = language


def extract_clang_graph(
    *,
    project: str,
    version: str,
    project_root: Path,
    language: str,
    api_roots: Iterable[Path],
    parse: ParseOptions,
    feature_set: str,
    clang_executable: str,
    work_directory: Path,
) -> ApiGraph:
    """Extract one feature set of a C or C++ unit with Clang's semantic frontend."""

    roots = tuple(path.resolve() for path in api_roots)
    missing = [root for root in roots if not root.is_dir()]
    if missing:
        raise RuntimeError(
            "API roots named in the feature-set manifest do not exist:\n"
            + "\n".join(f"  - {root}" for root in missing)
        )
    headers = _public_headers(roots)
    graph = ApiGraph(project=project, version=version, language="cpp")
    for header in headers:
        try:
            graph.sources[_logical_public_path(header, roots, project_root)] = header.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeDecodeError):
            pass
    if not headers:
        _relabel(graph, language)
        return graph

    work_directory.mkdir(parents=True, exist_ok=True)
    parser_language = parse.language
    umbrella = work_directory / ("cpdocs-api.c" if parser_language == "c" else "cpdocs-api.cpp")
    _write_umbrella(umbrella, headers)
    cwd, frontend_args = _parse_arguments(parse, language=parser_language, api_roots=roots)

    command = [
        clang_executable,
        *frontend_args,
        "-fparse-all-comments",
        "-Wno-unknown-warning-option",
        "-Wno-ignored-attributes",
        "-Xclang",
        "-ast-dump=json",
        "-fsyntax-only",
        str(umbrella),
    ]
    result = subprocess.run(
        command,
        cwd=cwd or project_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Clang semantic API extraction failed for feature set {feature_set!r}:\n"
            + " ".join(command)
            + "\n\n"
            + result.stderr.strip()
        )
    try:
        tree = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Clang returned invalid AST JSON for feature set {feature_set!r}: {error}"
        ) from error
    if not isinstance(tree, dict):
        raise RuntimeError(f"Clang returned an unexpected AST root for feature set {feature_set!r}")

    _walk_ast(
        tree,
        graph=graph,
        project_root=project_root,
        public_roots=roots,
        file_state=[None],
    )

    # The semantic AST deliberately does not represent macros as declarations. Discover only the
    # source macros that are active under this exact Clang configuration so conditional macros get
    # the same feature-set-aware availability semantics as declarations.
    active_macros = _active_macro_definitions(
        clang_executable=clang_executable,
        frontend_args=frontend_args,
        umbrella=umbrella,
        cwd=cwd or project_root,
    )
    for entity in _macro_candidates(headers, project_root, roots, active_macros):
        graph.add(entity)

    graph.rebuild_children()
    _relabel(graph, language)
    graph.rebuild_children()
    return graph
