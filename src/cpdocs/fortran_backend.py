# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Small source extractor for public Fortran module APIs.

The backend intentionally starts from source syntax rather than compiler-specific ``.mod`` files.
It covers the stable surface cpdocs needs for documentation: modules, derived types, functions and
subroutines, their argument names/types, source locations, and nearby ``!>``/``!!`` documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

from .model import (
    ApiEntity,
    ApiGraph,
    ApiParameter,
    ApiSignature,
    SourceLocation,
    relative_source_path,
    stable_entity_id,
)

_FORTRAN_SUFFIXES = {".f", ".for", ".ftn", ".f77", ".f90", ".f95", ".f03", ".f08", ".f18"}
_MODULE = re.compile(r"^\s*module\s+(?!procedure\b)([a-z_]\w*)\b", re.IGNORECASE)
_END_MODULE = re.compile(r"^\s*end\s*module\b", re.IGNORECASE)
_TYPE = re.compile(r"^\s*type\s*(?:,\s*([^:]+))?\s*::\s*([a-z_]\w*)\b", re.IGNORECASE)
_ROUTINE = re.compile(
    r"^\s*(.*?)\b(function|subroutine)\s+([a-z_]\w*)\s*\(([^)]*)\)\s*(?:result\s*\(\s*([a-z_]\w*)\s*\))?",
    re.IGNORECASE,
)
_END_ROUTINE = re.compile(r"^\s*end\s*(?:function|subroutine)\b", re.IGNORECASE)
_VISIBILITY = re.compile(r"^\s*(public|private)\s*(?:::\s*(.*))?$", re.IGNORECASE)
_DECL = re.compile(r"^\s*([^!]+?)\s*::\s*(.+)$")
_DOC = re.compile(r"^\s*!+[>]?[ ]?(.*)$")


def _source_files(roots: list[Path]) -> list[Path]:
    values: set[Path] = set()
    for root in roots:
        if root.is_file():
            if root.suffix.casefold() in _FORTRAN_SUFFIXES:
                values.add(root.resolve())
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in _FORTRAN_SUFFIXES:
                values.add(path.resolve())
    return sorted(values)


def _documentation(lines: list[str], line_index: int) -> str:
    values: list[str] = []
    index = line_index - 1
    while index >= 0:
        text = lines[index]
        if not text.strip():
            if values:
                break
            index -= 1
            continue
        match = _DOC.match(text)
        if not match:
            break
        values.append(match.group(1).strip())
        index -= 1
    values.reverse()
    return "\n".join(value for value in values if value)


def _names(text: str) -> list[str]:
    return [part.strip().casefold() for part in text.split(",") if part.strip()]


def _declaration_type(prefix: str) -> str:
    value = prefix.strip()
    # Remove routine attributes while preserving the declared result type.
    value = re.sub(
        r"\b(?:pure|elemental|recursive|impure|module)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip()


def _argument_types(lines: list[str], start: int, end: int, arguments: list[str]) -> dict[str, str]:
    wanted = {name.casefold() for name in arguments}
    result: dict[str, str] = {}
    for text in lines[start:end]:
        code = text.split("!", 1)[0].strip()
        match = _DECL.match(code)
        if not match:
            continue
        declaration = re.sub(r"\s+", " ", match.group(1).strip())
        # Intent/optional/value are argument attributes, not part of the type shown in compact API.
        type_text = re.split(
            r"\s*,\s*(?:intent\s*\(|optional\b|value\b)",
            declaration,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        for item in match.group(2).split(","):
            name = item.split("=", 1)[0].strip()
            name = re.sub(r"\([^)]*\)$", "", name).strip()
            lowered = name.casefold()
            if lowered in wanted:
                result[lowered] = type_text
    return result


def _routine_end(lines: list[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        if _END_ROUTINE.match(lines[index].split("!", 1)[0]):
            return index
    return len(lines)


def _public(
    name: str,
    *,
    default_public: bool,
    public: set[str],
    private: set[str],
    inline_public: bool = False,
    inline_private: bool = False,
) -> bool:
    lowered = name.casefold()
    if inline_private or lowered in private:
        return False
    if inline_public or lowered in public:
        return True
    return default_public


def extract_fortran_graph(
    *,
    project: str,
    version: str,
    project_root: Path,
    api_roots: list[Path],
    feature_set: str,
) -> ApiGraph:
    """Extract public module/type/routine declarations from Fortran source roots."""

    graph = ApiGraph(project=project, version=version, language="fortran")
    for path in _source_files(api_roots):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        logical = relative_source_path(path, project_root)
        graph.sources.setdefault(logical, content)
        lines = content.splitlines()

        module_name: str | None = None
        module_id: str | None = None
        default_public = True
        public_names: set[str] = set()
        private_names: set[str] = set()

        index = 0
        while index < len(lines):
            raw = lines[index]
            code = raw.split("!", 1)[0].strip()
            if not code:
                index += 1
                continue

            module_match = _MODULE.match(code)
            if module_match:
                module_name = module_match.group(1)
                module_id = stable_entity_id("fortran", "module", module_name)
                graph.add(
                    ApiEntity(
                        id=module_id,
                        language="fortran",
                        kind="module",
                        name=module_name,
                        qualified_name=module_name,
                        documentation=_documentation(lines, index),
                        source=SourceLocation(logical, index + 1, 1),
                        feature_sets=[feature_set],
                    )
                )
                index += 1
                continue
            if _END_MODULE.match(code):
                module_name = None
                module_id = None
                index += 1
                continue
            if module_name is None or module_id is None:
                index += 1
                continue

            visibility = _VISIBILITY.match(code)
            if visibility:
                names = visibility.group(2)
                is_public = visibility.group(1).casefold() == "public"
                if names:
                    target = public_names if is_public else private_names
                    target.update(_names(names))
                else:
                    default_public = is_public
                index += 1
                continue

            type_match = _TYPE.match(code)
            if type_match:
                attributes = (type_match.group(1) or "").casefold()
                name = type_match.group(2)
                if _public(
                    name,
                    default_public=default_public,
                    public=public_names,
                    private=private_names,
                    inline_public="public" in attributes,
                    inline_private="private" in attributes,
                ):
                    qualified = f"{module_name}::{name}"
                    graph.add(
                        ApiEntity(
                            id=stable_entity_id("fortran", "derived_type", qualified),
                            language="fortran",
                            kind="derived_type",
                            name=name,
                            qualified_name=qualified,
                            parent=module_id,
                            declaration=code,
                            documentation=_documentation(lines, index),
                            source=SourceLocation(logical, index + 1, 1),
                            feature_sets=[feature_set],
                        )
                    )
                index += 1
                continue

            routine = _ROUTINE.match(code)
            if routine:
                prefix, kind_text, name, arguments_text, _result_name = routine.groups()
                end = _routine_end(lines, index)
                if _public(
                    name,
                    default_public=default_public,
                    public=public_names,
                    private=private_names,
                ):
                    arguments = [
                        value.strip() for value in arguments_text.split(",") if value.strip()
                    ]
                    types = _argument_types(lines, index + 1, end, arguments)
                    parameters = tuple(
                        ApiParameter(name=value, type=types.get(value.casefold(), ""))
                        for value in arguments
                    )
                    kind = "function" if kind_text.casefold() == "function" else "subroutine"
                    returns = _declaration_type(prefix) if kind_text.casefold() == "function" else ""
                    qualified = f"{module_name}::{name}"
                    signature = ApiSignature(
                        parameters=parameters,
                        returns=returns,
                        spelling=code,
                        documentation=_documentation(lines, index),
                        source=SourceLocation(logical, index + 1, 1),
                    )
                    graph.add(
                        ApiEntity(
                            id=stable_entity_id("fortran", kind, qualified),
                            language="fortran",
                            kind=kind,
                            name=name,
                            qualified_name=qualified,
                            parent=module_id,
                            signatures=[signature],
                            documentation=signature.documentation,
                            source=signature.source,
                            feature_sets=[feature_set],
                        )
                    )
                index = max(index + 1, end)
                continue

            index += 1

    graph.rebuild_children()
    return graph
