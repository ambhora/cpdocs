# SPDX-FileCopyrightText: 2026 cpdocs developers
#
# SPDX-License-Identifier: Apache-2.0
"""Static Python API backend.

This backend deliberately avoids importing the documented package.  It uses the standard AST as a
portable baseline; the language-neutral model means a Griffe-backed extractor can replace this
module later without changing rendering or versioning.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from .model import ApiEntity, ApiGraph, ApiParameter, ApiSignature, SourceLocation, stable_entity_id


def _annotation(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _default(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef, *, implicit_first: bool = False
) -> ApiSignature:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    if implicit_first and positional and positional[0].arg in {"self", "cls"}:
        positional = positional[1:]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    parameters: list[ApiParameter] = []
    posonly_count = len(args.posonlyargs)
    for index, (argument, default) in enumerate(zip(positional, defaults, strict=True)):
        parameters.append(
            ApiParameter(
                name=argument.arg,
                type=_annotation(argument.annotation),
                default=_default(default),
                kind="positional-only" if index < posonly_count else "positional",
            )
        )
    if args.vararg is not None:
        parameters.append(
            ApiParameter(
                name=args.vararg.arg,
                type=_annotation(args.vararg.annotation),
                kind="var-positional",
            )
        )
    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parameters.append(
            ApiParameter(
                name=argument.arg,
                type=_annotation(argument.annotation),
                default=_default(default),
                kind="keyword-only",
            )
        )
    if args.kwarg is not None:
        parameters.append(
            ApiParameter(
                name=args.kwarg.arg,
                type=_annotation(args.kwarg.annotation),
                kind="var-keyword",
            )
        )
    qualifiers: list[str] = []
    if isinstance(node, ast.AsyncFunctionDef):
        qualifiers.append("async")
    for decorator in node.decorator_list:
        text = _annotation(decorator)
        if text in {"classmethod", "staticmethod", "property", "abstractmethod"}:
            qualifiers.append(text)
        elif text.endswith(".overload") or text == "overload":
            qualifiers.append("overload")
    return ApiSignature(
        parameters=tuple(parameters),
        returns=_annotation(node.returns),
        qualifiers=tuple(dict.fromkeys(qualifiers)),
    )


def _module_info(root: Path, path: Path, package: str) -> tuple[str, str]:
    """Return the public module/package name and normalized entity kind for one source file."""

    relative = path.relative_to(root)
    parts = list(relative.with_suffix("").parts)
    is_package = bool(parts and parts[-1] == "__init__")
    if is_package:
        parts.pop()
    qualified = ".".join([package, *parts]) if parts else package
    return qualified, "package" if is_package else "module"


def _parent_qualified_name(qualified: str) -> str | None:
    return qualified.rsplit(".", 1)[0] if "." in qualified else None


def _public_names(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return None
        names: set[str] = set()
        for item in value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                names.add(item.value)
        return names
    return None


def _attribute_docstring(body: list[ast.stmt], index: int) -> str:
    """Docstring written as a string literal directly below an assignment (PEP 257)."""

    if index + 1 >= len(body):
        return ""
    following = body[index + 1]
    if (
        isinstance(following, ast.Expr)
        and isinstance(following.value, ast.Constant)
        and isinstance(following.value.value, str)
    ):
        return inspect.cleandoc(following.value.value)
    return ""


def _walk_body(
    body: list[ast.stmt],
    *,
    graph: ApiGraph,
    module: str,
    source_path: str,
    parent: ApiEntity,
    scopes: tuple[str, ...],
    explicit_public: set[str] | None = None,
) -> None:
    for index, node in enumerate(body):
        entity: ApiEntity | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            in_class = parent.kind in {"class", "protocol", "enum"}
            if (
                node.name.startswith("_")
                and node.name != "__init__"
                and (explicit_public is None or node.name not in explicit_public)
            ):
                continue
            qualified = ".".join((*scopes, node.name))
            kind = (
                "constructor"
                if in_class and node.name == "__init__"
                else ("method" if in_class else "function")
            )
            signature = _signature(node, implicit_first=in_class)
            properties = list(signature.qualifiers)
            if "property" in properties:
                kind = "property"
            entity = ApiEntity(
                id=stable_entity_id("python", kind, qualified),
                language="python",
                kind=kind,
                name=node.name,
                qualified_name=qualified,
                parent=parent.id,
                signatures=[signature],
                documentation=ast.get_docstring(node, clean=True) or "",
                source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                properties=properties,
            )
            graph.add(entity)
            continue

        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_") and (
                explicit_public is None or node.name not in explicit_public
            ):
                continue
            qualified = ".".join((*scopes, node.name))
            bases = [_annotation(base) for base in node.bases]
            decorators = [_annotation(item) for item in node.decorator_list]
            properties = [value for value in decorators if value]
            if any(value.endswith("Protocol") or value == "Protocol" for value in bases):
                kind = "protocol"
            elif any(value.endswith("Enum") or value == "Enum" for value in bases):
                kind = "enum"
            else:
                kind = "class"
            entity = ApiEntity(
                id=stable_entity_id("python", kind, qualified),
                language="python",
                kind=kind,
                name=node.name,
                qualified_name=qualified,
                parent=parent.id,
                documentation=ast.get_docstring(node, clean=True) or "",
                source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                properties=properties,
                bases=[base for base in bases if base],
            )
            graph.add(entity)
            _walk_body(
                node.body,
                graph=graph,
                module=module,
                source_path=source_path,
                parent=graph.entities[entity.id],
                scopes=(*scopes, node.name),
            )
            continue

        if parent.kind == "enum" and isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name) or target.id.startswith("_"):
                    continue
                name = target.id
                qualified = ".".join((*scopes, name))
                graph.add(
                    ApiEntity(
                        id=stable_entity_id("python", "constant", qualified),
                        language="python",
                        kind="constant",
                        name=name,
                        qualified_name=qualified,
                        parent=parent.id,
                        source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                        documentation=_attribute_docstring(body, index),
                        properties=[_default(node.value) or ""],
                    )
                )
            continue

        # PEP 695 ``type Alias = ...`` (Python 3.12+) is represented explicitly in the AST.
        type_alias_cls = getattr(ast, "TypeAlias", None)
        if type_alias_cls is not None and isinstance(node, type_alias_cls):
            name_node = getattr(node, "name", None)
            name = getattr(name_node, "id", None)
            if isinstance(name, str) and not name.startswith("_"):
                qualified = ".".join((*scopes, name))
                target = _annotation(getattr(node, "value", None))
                graph.add(
                    ApiEntity(
                        id=stable_entity_id("python", "type_alias", qualified),
                        language="python",
                        kind="type_alias",
                        name=name,
                        qualified_name=qualified,
                        parent=parent.id,
                        source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                        documentation=_attribute_docstring(body, index),
                        properties=[f"= {target}"] if target else [],
                    )
                )
            continue

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                name = target.id
                if name.startswith("_") and (
                    explicit_public is None or name not in explicit_public
                ):
                    continue
                # Ordinary module/class assignments are useful API constants when explicitly public.
                # Avoid documenting imports/cache helpers merely because they are assigned.
                if not (
                    name.isupper() or (explicit_public is not None and name in explicit_public)
                ):
                    continue
                qualified = ".".join((*scopes, name))
                value = _default(node.value)
                graph.add(
                    ApiEntity(
                        id=stable_entity_id("python", "constant", qualified),
                        language="python",
                        kind="constant",
                        name=name,
                        qualified_name=qualified,
                        parent=parent.id,
                        source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                        documentation=_attribute_docstring(body, index),
                        properties=[f"= {value}"] if value else [],
                    )
                )
            continue

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if name.startswith("_") and (explicit_public is None or name not in explicit_public):
                continue
            qualified = ".".join((*scopes, name))
            annotation = _annotation(node.annotation)
            is_alias = annotation in {
                "TypeAlias",
                "typing.TypeAlias",
                "typing_extensions.TypeAlias",
            }
            kind = "type_alias" if is_alias else ("constant" if name.isupper() else "attribute")
            properties: list[str] = []
            if not is_alias and annotation:
                properties.append(annotation)
            value = _default(node.value)
            if value is not None:
                properties.append(f"= {value}")
            entity = ApiEntity(
                id=stable_entity_id("python", kind, qualified),
                language="python",
                kind=kind,
                name=name,
                qualified_name=qualified,
                parent=parent.id,
                documentation=_attribute_docstring(body, index),
                source=SourceLocation(source_path, node.lineno, node.col_offset + 1),
                properties=properties,
            )
            graph.add(entity)


def build_python_graph(
    *,
    project_root: Path,
    package_root: Path,
    package: str,
    version: str = "main",
    include_private: bool = False,
) -> ApiGraph:
    """Build a static Python API graph without importing the documented package."""

    project_root = project_root.resolve()
    package_root = package_root.resolve()
    graph = ApiGraph(project=package, version=version, language="python")
    try:
        source_root = package_root.parent.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        source_root = ""
    if source_root not in {"", "."}:
        graph.metadata["source_root"] = source_root

    package_entity = ApiEntity(
        id=stable_entity_id("python", "package", package),
        language="python",
        kind="package",
        name=package.rsplit(".", 1)[-1],
        qualified_name=package,
    )
    graph.add(package_entity)

    def public_source(path: Path) -> bool:
        parts = path.relative_to(package_root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            return False
        if include_private:
            return True
        # ``__init__`` defines a package's public surface. Other underscore-prefixed modules are
        # implementation details unless ``api.hide.python-modules: none`` opts them in.
        return path.name == "__init__.py" or (
            not path.stem.startswith("_") and all(not part.startswith("_") for part in parts[:-1])
        )

    sources = sorted(
        {
            path
            for suffix in ("*.py", "*.pyi")
            for path in package_root.rglob(suffix)
            if public_source(path)
        },
        key=lambda path: (path.relative_to(package_root).as_posix(), path.suffix != ".py"),
    )

    parsed: list[tuple[Path, ast.Module, str, str, str]] = []
    # Create the module/package hierarchy first so children can always refer to a semantic parent.
    for path in sources:
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path), type_comments=True
            )
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            raise RuntimeError(f"Cannot parse Python API source {path}: {error}") from error
        qualified, kind = _module_info(package_root, path, package)
        try:
            source_path = path.relative_to(project_root).as_posix()
        except ValueError:
            source_path = path.as_posix()
        parsed.append((path, tree, qualified, kind, source_path))
        try:
            graph.sources.setdefault(source_path, path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            pass

        if qualified == package:
            root = graph.entities[package_entity.id]
            if not root.documentation:
                root.documentation = ast.get_docstring(tree, clean=True) or ""
            if root.source is None:
                root.source = SourceLocation(source_path, 1, 1)
            continue

        parent_name = _parent_qualified_name(qualified) or package
        parent_id = stable_entity_id(
            "python",
            "package"
            if (package_root / Path(*parent_name.split(".")[1:]) / "__init__.py").is_file()
            else "module",
            parent_name,
        )
        if parent_id not in graph.entities:
            # Namespace-package directories need no __init__.py. Represent the missing container as a
            # package so the API tree remains hierarchical without importing it.
            parent_id = stable_entity_id("python", "package", parent_name)
            graph.add(
                ApiEntity(
                    id=parent_id,
                    language="python",
                    kind="package",
                    name=parent_name.rsplit(".", 1)[-1],
                    qualified_name=parent_name,
                    parent=package_entity.id if parent_name != package else None,
                )
            )
        entity_id = stable_entity_id("python", kind, qualified)
        graph.add(
            ApiEntity(
                id=entity_id,
                language="python",
                kind=kind,
                name=qualified.rsplit(".", 1)[-1],
                qualified_name=qualified,
                parent=parent_id,
                documentation=ast.get_docstring(tree, clean=True) or "",
                source=SourceLocation(source_path, 1, 1),
            )
        )

    for _path, tree, qualified, kind, source_path in parsed:
        if qualified == package:
            parent = graph.entities[package_entity.id]
        else:
            parent = graph.entities[stable_entity_id("python", kind, qualified)]
        _walk_body(
            tree.body,
            graph=graph,
            module=qualified,
            source_path=source_path,
            parent=parent,
            scopes=tuple(qualified.split(".")),
            explicit_public=_public_names(tree),
        )

    graph.rebuild_children()
    return graph
