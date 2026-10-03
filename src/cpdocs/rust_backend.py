# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Rustdoc-JSON backend for the shared cpdocs API graph."""

from __future__ import annotations

import json
from pathlib import Path

from .model import ApiEntity, ApiGraph, ApiParameter, ApiSignature, SourceLocation, stable_entity_id

_KIND_MAP = {
    "module": "module",
    "struct": "struct",
    "enum": "enum",
    "trait": "trait",
    "function": "function",
    "type_alias": "type_alias",
    "constant": "constant",
    "static": "variable",
    "macro": "macro",
    "proc_macro": "macro",
    "union": "union",
}


def _rust_type(value: object) -> str:
    """Render the stable, user-facing portion of a rustdoc JSON type node."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(filter(None, (_rust_type(item) for item in value)))
    if not isinstance(value, dict) or not value:
        return ""
    if "primitive" in value:
        return str(value["primitive"])
    if "generic" in value:
        return str(value["generic"])
    if "infer" in value:
        return "_"
    if "slice" in value:
        return f"[{_rust_type(value['slice'])}]"
    if "array" in value and isinstance(value["array"], dict):
        array = value["array"]
        length = array.get("len", "_")
        return f"[{_rust_type(array.get('type'))}; {length}]"
    if "tuple" in value:
        parts = value["tuple"] if isinstance(value["tuple"], list) else []
        rendered = ", ".join(_rust_type(item) for item in parts)
        if len(parts) == 1:
            rendered += ","
        return f"({rendered})"
    if "borrowed_ref" in value and isinstance(value["borrowed_ref"], dict):
        ref = value["borrowed_ref"]
        lifetime = ref.get("lifetime")
        lifetime_text = f"'{lifetime} " if isinstance(lifetime, str) and lifetime else ""
        mutable = "mut " if ref.get("is_mutable") else ""
        return f"&{lifetime_text}{mutable}{_rust_type(ref.get('type'))}"
    if "raw_pointer" in value and isinstance(value["raw_pointer"], dict):
        pointer = value["raw_pointer"]
        qualifier = "mut" if pointer.get("is_mutable") else "const"
        return f"*{qualifier} {_rust_type(pointer.get('type'))}"
    if "resolved_path" in value and isinstance(value["resolved_path"], dict):
        path = value["resolved_path"]
        name = str(path.get("name", ""))
        args = path.get("args")
        rendered_args: list[str] = []
        if isinstance(args, dict):
            angle = args.get("angle_bracketed")
            if isinstance(angle, dict):
                raw_args = angle.get("args")
                if isinstance(raw_args, list):
                    for argument in raw_args:
                        if not isinstance(argument, dict):
                            continue
                        if "type" in argument:
                            rendered_args.append(_rust_type(argument["type"]))
                        elif "lifetime" in argument:
                            rendered_args.append(str(argument["lifetime"]))
                        elif "const" in argument:
                            rendered_args.append(str(argument["const"]))
        if rendered_args:
            name += "<" + ", ".join(rendered_args) + ">"
        return name
    if "impl_trait" in value:
        bounds = value["impl_trait"] if isinstance(value["impl_trait"], list) else []
        return "impl " + " + ".join(filter(None, (_rust_type(item) for item in bounds)))
    if "dyn_trait" in value:
        traits = value["dyn_trait"] if isinstance(value["dyn_trait"], list) else []
        return "dyn " + " + ".join(filter(None, (_rust_type(item) for item in traits)))
    # rustdoc evolves its JSON schema. Unknown type variants stay localized to this adapter rather
    # than leaking backend-specific structure into ApiGraph or the renderer.
    return next((_rust_type(item) for item in value.values() if _rust_type(item)), "")


def _function_signature(item: dict[str, object]) -> tuple[ApiSignature | None, list[str]]:
    inner = item.get("inner")
    if not isinstance(inner, dict):
        return None, []
    function = inner.get("function")
    if not isinstance(function, dict):
        return None, []
    signature = function.get("sig")
    parameters: list[ApiParameter] = []
    returns = ""
    if isinstance(signature, dict):
        inputs = signature.get("inputs")
        if isinstance(inputs, list):
            for raw in inputs:
                if isinstance(raw, list) and len(raw) >= 2:
                    parameters.append(ApiParameter(name=str(raw[0]), type=_rust_type(raw[1])))
        returns = _rust_type(signature.get("output"))
    properties: list[str] = ["pub"]
    header = function.get("header")
    if isinstance(header, dict):
        for field, label in (("is_const", "const"), ("is_async", "async"), ("is_unsafe", "unsafe")):
            if header.get(field):
                properties.append(label)
        abi = header.get("abi")
        if isinstance(abi, str) and abi not in {"", "Rust"}:
            properties.append(f'extern "{abi}"')
    return ApiSignature(
        parameters=tuple(parameters), returns=returns, qualifiers=tuple(properties[1:])
    ), properties


def _inner_kind(item: dict[str, object]) -> str | None:
    inner = item.get("inner")
    if not isinstance(inner, dict) or not inner:
        return None
    return next(iter(inner))


def build_rust_graph(
    *, rustdoc_json: Path, project: str, version: str = "main", project_root: Path | None = None
) -> ApiGraph:
    try:
        raw = json.loads(rustdoc_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read rustdoc JSON {rustdoc_json}: {error}") from error
    if not isinstance(raw, dict):
        raise RuntimeError(f"Unexpected rustdoc JSON root in {rustdoc_json}")

    index = raw.get("index")
    paths = raw.get("paths")
    if not isinstance(index, dict) or not isinstance(paths, dict):
        raise RuntimeError("rustdoc JSON does not contain index/paths maps")

    graph = ApiGraph(project=project, version=version, language="rust")
    rust_to_entity: dict[str, str] = {}
    path_to_id: dict[str, str] = {}

    for rust_id, raw_item in index.items():
        if not isinstance(raw_item, dict):
            continue
        visibility = raw_item.get("visibility")
        if visibility not in {"public", None} and not (
            isinstance(visibility, dict) and "public" in visibility
        ):
            continue
        kind_value = _inner_kind(raw_item)
        kind = _KIND_MAP.get(kind_value or "")
        if kind is None:
            continue
        path_info = paths.get(rust_id)
        path_values = path_info.get("path") if isinstance(path_info, dict) else None
        if isinstance(path_values, list) and path_values:
            qualified = "::".join(str(value) for value in path_values)
        else:
            name = raw_item.get("name")
            if not isinstance(name, str) or not name:
                continue
            qualified = name
        name = str(raw_item.get("name") or qualified.rsplit("::", 1)[-1])
        entity_id = stable_entity_id("rust", kind, qualified)
        source = None
        span = raw_item.get("span")
        if isinstance(span, dict) and isinstance(span.get("filename"), str):
            filename = Path(str(span["filename"]))
            if project_root is not None:
                try:
                    filename_text = (
                        filename.resolve().relative_to(project_root.resolve()).as_posix()
                    )
                except (OSError, ValueError):
                    filename_text = filename.as_posix()
            else:
                filename_text = filename.as_posix()
            begin = span.get("begin")
            line = None
            column = None
            if isinstance(begin, list) and len(begin) >= 2:
                if isinstance(begin[0], int):
                    line = begin[0]
                if isinstance(begin[1], int):
                    column = begin[1]
            source = SourceLocation(filename_text, line, column)
            if project_root is not None:
                physical = filename if filename.is_absolute() else project_root / filename
                try:
                    graph.sources.setdefault(filename_text, physical.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    pass
        function_signature, function_properties = _function_signature(raw_item)
        entity = ApiEntity(
            id=entity_id,
            language="rust",
            kind=kind,
            name=name,
            qualified_name=qualified,
            signatures=[function_signature] if function_signature is not None else [],
            documentation=str(raw_item.get("docs") or ""),
            source=source,
            properties=function_properties or ["pub"],
        )
        graph.add(entity)
        rust_to_entity[str(rust_id)] = entity_id
        path_to_id[qualified] = entity_id

    # Infer hierarchy from semantic paths. rustdoc ids are deliberately not exposed outside this
    # adapter; renderer URLs depend only on the normalized cpdocs identity.
    for entity in graph.entities.values():
        parent_path = (
            entity.qualified_name.rsplit("::", 1)[0] if "::" in entity.qualified_name else ""
        )
        parent = path_to_id.get(parent_path)
        if parent and parent != entity.id:
            entity.parent = parent

    graph.rebuild_children()
    return graph
