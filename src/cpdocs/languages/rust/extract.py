# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Rustdoc-JSON backend for the shared cpdocs API graph."""

from __future__ import annotations

import json
from pathlib import Path

from ...model import ApiEntity, ApiGraph, ApiParameter, ApiSignature, SourceLocation, stable_entity_id

_KIND_MAP = {
    "module": "module",
    "struct": "struct",
    "struct_field": "field",
    "enum": "enum",
    "variant": "enum_value",
    "trait": "trait",
    "trait_alias": "trait_alias",
    "function": "function",
    "type_alias": "type_alias",
    "constant": "constant",
    "assoc_const": "constant",
    "assoc_type": "type_alias",
    "static": "variable",
    "macro": "macro",
    "proc_macro": "macro",
    "proc_attribute": "macro",
    "proc_derive": "macro",
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
        name = str(path.get("path") or path.get("name") or "")
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
    properties: list[str] = []
    header = function.get("header")
    if isinstance(header, dict):
        for field, label in (("is_const", "const"), ("is_async", "async"), ("is_unsafe", "unsafe")):
            if header.get(field):
                properties.append(label)
        abi = header.get("abi")
        if isinstance(abi, str) and abi.casefold() not in {"", "rust"}:
            properties.append(f'extern "{abi}"')
    return ApiSignature(
        parameters=tuple(parameters), returns=returns, qualifiers=tuple(properties)
    ), properties


def _inner_kind(item: dict[str, object]) -> str | None:
    inner = item.get("inner")
    if not isinstance(inner, dict) or not inner:
        return None
    return next(iter(inner))


def _visibility(item: dict[str, object]) -> str:
    value = item.get("visibility")
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, dict) and value:
        return str(next(iter(value))).casefold()
    # Older fixtures and early rustdoc JSON experiments did not always carry visibility. Keep
    # accepting those inputs; current rustdoc output always has the field.
    return "public"


def _id_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _inner_payload(item: dict[str, object], kind: str) -> object:
    inner = item.get("inner")
    if not isinstance(inner, dict):
        return None
    return inner.get(kind)


def _aggregate_children(item: dict[str, object]) -> list[str]:
    """Return item ids that are semantically owned by this declaration.

    rustdoc's ``paths`` map is a lookup/linking aid; it is not a reliable ownership tree for
    associated items such as struct fields.  The item payloads themselves carry that relationship.
    """

    kind = _inner_kind(item)
    payload = _inner_payload(item, kind or "")
    if not isinstance(payload, dict):
        return []
    if kind in {"module", "trait"}:
        return _id_list(payload.get("items"))
    if kind == "union":
        return _id_list(payload.get("fields"))
    if kind == "enum":
        return _id_list(payload.get("variants"))
    if kind in {"struct", "variant"}:
        shape = payload.get("kind")
        if not isinstance(shape, dict) or not shape:
            return []
        tag, data = next(iter(shape.items()))
        if tag in {"plain", "struct"} and isinstance(data, dict):
            return _id_list(data.get("fields"))
        if tag == "tuple":
            return _id_list(data)
    return []


def _resolved_path_id(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    resolved = value.get("resolved_path")
    if not isinstance(resolved, dict) or resolved.get("id") is None:
        return None
    return str(resolved["id"])


def _ownership(index: dict[str, object]) -> tuple[dict[str, str], set[str], set[str]]:
    """Build semantic ownership for fields, variants, trait items and inherent impl items.

    Trait-implementation bodies are deliberately not emitted as separate API declarations: the
    trait already owns those declarations, while an inherent impl contributes methods/associated
    items to the implemented type.
    """

    owners: dict[str, str] = {}
    inherent_impl_items: set[str] = set()
    trait_impl_items: set[str] = set()

    for owner_id, raw_item in index.items():
        if not isinstance(raw_item, dict):
            continue
        for child_id in _aggregate_children(raw_item):
            owners.setdefault(child_id, str(owner_id))

    for raw_item in index.values():
        if not isinstance(raw_item, dict) or _inner_kind(raw_item) != "impl":
            continue
        payload = _inner_payload(raw_item, "impl")
        if not isinstance(payload, dict):
            continue
        items = _id_list(payload.get("items"))
        if payload.get("trait") is not None:
            trait_impl_items.update(items)
            continue
        target_id = _resolved_path_id(payload.get("for"))
        if target_id is None:
            continue
        for child_id in items:
            owners[child_id] = target_id
            inherent_impl_items.add(child_id)

    return owners, inherent_impl_items, trait_impl_items

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

    root_id = str(raw.get("root") or "")
    root_item = index.get(root_id)
    local_crate_id = root_item.get("crate_id") if isinstance(root_item, dict) else None
    owner_by_item, inherent_impl_items, trait_impl_items = _ownership(index)

    qualified_cache: dict[str, str] = {}
    resolving: set[str] = set()

    def qualified_name(rust_id: str, item: dict[str, object]) -> str:
        cached = qualified_cache.get(rust_id)
        if cached is not None:
            return cached

        name = item.get("name")
        name_text = name if isinstance(name, str) else ""
        owner_id = owner_by_item.get(rust_id)
        if owner_id is not None and owner_id != rust_id and rust_id not in resolving:
            owner = index.get(owner_id)
            if isinstance(owner, dict) and name_text:
                resolving.add(rust_id)
                owner_name = qualified_name(owner_id, owner)
                resolving.discard(rust_id)
                if owner_name:
                    result = f"{owner_name}::{name_text}"
                    qualified_cache[rust_id] = result
                    return result

        path_info = paths.get(rust_id)
        path_values = path_info.get("path") if isinstance(path_info, dict) else None
        if isinstance(path_values, list) and path_values:
            result = "::".join(str(value) for value in path_values)
        else:
            result = name_text
        qualified_cache[rust_id] = result
        return result

    graph = ApiGraph(project=project, version=version, language="rust")
    rust_to_entity: dict[str, str] = {}
    path_to_id: dict[str, str] = {}

    for raw_rust_id, raw_item in index.items():
        rust_id = str(raw_rust_id)
        if not isinstance(raw_item, dict):
            continue
        if local_crate_id is not None and raw_item.get("crate_id") != local_crate_id:
            continue
        # Methods/associated items in trait impls are implementations of declarations already owned
        # by the trait.  Rendering them as free API items produces entries such as clone()/eq()/fmt()
        # at crate scope and can collide across traits.
        if rust_id in trait_impl_items:
            continue
        visibility = _visibility(raw_item)
        # ``default`` is part of the public API for e.g. public trait members and enum variants.
        if visibility not in {"public", "default"}:
            continue
        kind_value = _inner_kind(raw_item)
        kind = _KIND_MAP.get(kind_value or "")
        if kind is None:
            continue
        if rust_id in inherent_impl_items and kind == "function":
            kind = "method"
        qualified = qualified_name(rust_id, raw_item)
        if not qualified:
            continue
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
        properties = (["pub"] if visibility == "public" else []) + function_properties
        entity = ApiEntity(
            id=entity_id,
            language="rust",
            kind=kind,
            name=name,
            qualified_name=qualified,
            signatures=[function_signature] if function_signature is not None else [],
            documentation=str(raw_item.get("docs") or ""),
            source=source,
            properties=properties,
        )
        graph.add(entity)
        rust_to_entity[rust_id] = entity_id
        path_to_id[qualified] = entity_id

    # Prefer rustdoc's explicit ownership relationships.  ``paths`` is useful for linking but does
    # not reliably encode the owner of fields and associated items.
    for rust_id, entity_id in rust_to_entity.items():
        entity = graph.entities[entity_id]
        owner_id = owner_by_item.get(rust_id)
        parent = rust_to_entity.get(owner_id or "")
        if parent and parent != entity.id:
            entity.parent = parent
            continue
        parent_path = (
            entity.qualified_name.rsplit("::", 1)[0] if "::" in entity.qualified_name else ""
        )
        parent = path_to_id.get(parent_path)
        if parent and parent != entity.id:
            entity.parent = parent

    graph.rebuild_children()
    return graph
