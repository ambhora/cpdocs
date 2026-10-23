# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Static Python API backend.

This backend deliberately avoids importing the documented package.  It uses the standard AST as a
portable baseline; the language-neutral model means a Griffe-backed extractor can replace this
module later without changing rendering or versioning.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Any

from ...contract import UnitManifest
from ...filesystem import readable_file
from ...model import (
    ApiEntity,
    ApiGraph,
    ApiParameter,
    ApiSignature,
    SourceLocation,
    relative_source_path,
    stable_entity_id,
)
from ..unit import UnitContext


def _version_imports(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Find straightforward aliases without executing source code."""

    sys_names = {"sys"}  # Standard spelling, even if imports are outside the current module.
    version_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    sys_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "sys" and node.level == 0:
            for alias in node.names:
                if alias.name == "version_info":
                    version_names.add(alias.asname or alias.name)
    return sys_names, version_names


def _guard_value(node: ast.expr, version: tuple[int, int], sys_names: set[str], version_names: set[str]) -> Any:
    """Evaluate only literals and standard Python interpreter-version references."""

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, str, bool)):
        return node.value
    if isinstance(node, ast.Tuple):
        items = [_guard_value(item, version, sys_names, version_names) for item in node.elts]
        if any(item is None for item in items):
            return None
        return tuple(items)
    is_version_info = (isinstance(node, ast.Name) and node.id in version_names) or (
        isinstance(node, ast.Attribute)
        and node.attr == "version_info"
        and isinstance(node.value, ast.Name)
        and node.value.id in sys_names
    )
    if is_version_info:
        # Python's sys.version_info tuple has five entries; comparisons against shorter
        # tuples use normal tuple ordering. A stable release is our explicit assumption.
        return (*version, 0, "final", 0)
    if isinstance(node, ast.Subscript):
        value = _guard_value(node.value, version, sys_names, version_names)
        if not isinstance(value, tuple):
            return None
        if isinstance(node.slice, ast.Slice):
            bounds = (node.slice.lower, node.slice.upper, node.slice.step)
            if any(bound is not None and not isinstance(bound, ast.Constant) for bound in bounds):
                return None
            args = [bound.value if bound is not None else None for bound in bounds]
            if not all(arg is None or type(arg) is int for arg in args):
                return None
            return value[slice(*args)]
        index = _guard_value(node.slice, version, sys_names, version_names)
        if type(index) is int and -len(value) <= index < len(value):
            return value[index]
    if isinstance(node, ast.Attribute) and node.attr in {"major", "minor", "micro"}:
        value = _guard_value(node.value, version, sys_names, version_names)
        if isinstance(value, tuple) and len(value) == 5:
            return value[{"major": 0, "minor": 1, "micro": 2}[node.attr]]
    return None


def _version_guard(
    node: ast.expr, version: tuple[int, int] | None, sys_names: set[str], version_names: set[str]
) -> bool | None:
    """Resolve safe native version tests; unknown conditions remain undecidable."""

    if version is None:
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        result = _version_guard(node.operand, version, sys_names, version_names)
        return None if result is None else not result
    if isinstance(node, ast.BoolOp):
        results = [_version_guard(value, version, sys_names, version_names) for value in node.values]
        if isinstance(node.op, ast.And):
            if False in results:
                return False
            return True if all(value is True for value in results) else None
        if isinstance(node.op, ast.Or):
            if True in results:
                return True
            return False if all(value is False for value in results) else None
        return None
    if isinstance(node, ast.Compare):
        operands = [node.left, *node.comparators]
        values = [_guard_value(item, version, sys_names, version_names) for item in operands]
        if any(value is None for value in values):
            return None
        for left, operation, right in zip(values[:-1], node.ops, values[1:], strict=True):
            try:
                if isinstance(operation, ast.GtE):
                    result = left >= right
                elif isinstance(operation, ast.Gt):
                    result = left > right
                elif isinstance(operation, ast.LtE):
                    result = left <= right
                elif isinstance(operation, ast.Lt):
                    result = left < right
                elif isinstance(operation, ast.Eq):
                    result = left == right
                elif isinstance(operation, ast.NotEq):
                    result = left != right
                else:
                    return None
            except TypeError:
                return None
            if not result:
                return False
        return True
    return None


def _selected_body(
    body: list[ast.stmt], version: tuple[int, int] | None, sys_names: set[str], version_names: set[str]
) -> list[ast.stmt]:
    """Flatten resolvable version branches; omit unknown conditions (legacy behavior).

    Unknown guards are intentionally *not* interpreted as unconditional availability.
    Providers for projects with dynamic conditional exports should emit their own manifests.
    """

    selected: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.If):
            decision = _version_guard(node.test, version, sys_names, version_names)
            if decision is not None:
                selected.extend(
                    _selected_body(node.body if decision else node.orelse, version, sys_names, version_names)
                )
            continue
        selected.append(node)
    return selected


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


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef, *, implicit_first: bool = False) -> ApiSignature:
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
            ApiParameter(name=args.vararg.arg, type=_annotation(args.vararg.annotation), kind="var-positional")
        )
    for argument, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parameters.append(
            ApiParameter(
                name=argument.arg, type=_annotation(argument.annotation), default=_default(default), kind="keyword-only"
            )
        )
    if args.kwarg is not None:
        parameters.append(
            ApiParameter(name=args.kwarg.arg, type=_annotation(args.kwarg.annotation), kind="var-keyword")
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
        parameters=tuple(parameters), returns=_annotation(node.returns), qualifiers=tuple(dict.fromkeys(qualifiers))
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


def _public_names(
    tree: ast.Module, version: tuple[int, int] | None, sys_names: set[str], version_names: set[str]
) -> set[str] | None:
    for node in _selected_body(tree.body, version, sys_names, version_names):
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
    python_version: tuple[int, int] | None = None,
    sys_names: set[str] | None = None,
    version_names: set[str] | None = None,
) -> None:
    sys_names = sys_names or {"sys"}
    version_names = version_names or set()
    body = _selected_body(body, python_version, sys_names, version_names)
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
            kind = "constructor" if in_class and node.name == "__init__" else ("method" if in_class else "function")
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
            if node.name.startswith("_") and (explicit_public is None or node.name not in explicit_public):
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
                python_version=python_version,
                sys_names=sys_names,
                version_names=version_names,
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
                if name.startswith("_") and (explicit_public is None or name not in explicit_public):
                    continue
                # Ordinary module/class assignments are useful API constants when explicitly public.
                # Avoid documenting imports/cache helpers merely because they are assigned.
                if not (name.isupper() or (explicit_public is not None and name in explicit_public)):
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
            is_alias = annotation in {"TypeAlias", "typing.TypeAlias", "typing_extensions.TypeAlias"}
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
    python_version: tuple[int, int] | None = None,
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

    def package_source(path: Path) -> bool:
        parts = path.relative_to(package_root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            return False
        # A link out of the package and the project is not followed.
        return readable_file(path, (package_root, project_root))

    def public_source(path: Path) -> bool:
        if include_private:
            return True
        parts = path.relative_to(package_root).parts
        # ``__init__`` defines a package's public surface. Other underscore-prefixed modules are
        # implementation details unless ``api.hide.python-modules: none`` opts them in.
        return path.name == "__init__.py" or (
            not path.stem.startswith("_") and all(not part.startswith("_") for part in parts[:-1])
        )

    def importable_source(path: Path) -> bool:
        # A file whose name is not an identifier cannot be imported, so it is not API. Its name
        # would otherwise become a module name shown to readers, as in ``<img ...>.py``.
        parts = path.relative_to(package_root).with_suffix("").parts
        return all(part.isidentifier() for part in parts)

    every_source = sorted(
        {path for suffix in ("*.py", "*.pyi") for path in package_root.rglob(suffix) if package_source(path)},
        key=lambda path: (path.relative_to(package_root).as_posix(), path.suffix != ".py"),
    )
    sources = [path for path in every_source if public_source(path) and importable_source(path)]

    # Hidden modules are not part of the API, but they are files of the package: the file hierarchy
    # lists them and their source can be read like any other.
    for path in every_source:
        if public_source(path) and importable_source(path):
            continue
        try:
            graph.sources.setdefault(relative_source_path(path, project_root), path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            pass

    parsed: list[tuple[Path, ast.Module, str, str, str]] = []
    # Create the module/package hierarchy first so children can always refer to a semantic parent.
    for path in sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), type_comments=True)
        except (OSError, UnicodeDecodeError, SyntaxError) as error:
            raise RuntimeError(f"Cannot parse Python API source {path}: {error}") from error
        qualified, kind = _module_info(package_root, path, package)
        source_path = relative_source_path(path, project_root)
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
            "package" if (package_root / Path(*parent_name.split(".")[1:]) / "__init__.py").is_file() else "module",
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
        sys_names, version_names = _version_imports(tree)
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
            explicit_public=_public_names(tree, python_version, sys_names, version_names),
            python_version=python_version,
            sys_names=sys_names,
            version_names=version_names,
        )

    graph.rebuild_children()
    return graph


def target_python_version(language_configuration: dict[str, object]) -> tuple[int, int] | None:
    """The ``python.version`` of a language configuration as ``(major, minor)``, if it names one.

    The extractor evaluates ``sys.version_info`` guards for this version. Without one, guarded
    definitions are left out rather than guessed.
    """

    python = language_configuration.get("python")
    if not isinstance(python, dict) or "version" not in python:
        return None
    value = str(python["version"])
    if not re.fullmatch(r"[0-9]+\.[0-9]+", value):
        raise RuntimeError(f"cpdocs.yml: python.version must be MAJOR.MINOR, found {value!r}")
    major, minor = value.split(".")
    return int(major), int(minor)


def extract_unit(unit: UnitManifest, context: UnitContext) -> ApiGraph:
    """Extract a Python unit: read its one package statically, without importing it."""

    assert unit.package is not None
    return build_python_graph(
        project_root=context.project_root,
        package_root=unit.api[0].path,
        package=unit.package,
        version=context.version,
        include_private=not context.config.hide_private_python,
        python_version=target_python_version(context.language_configuration),
    )
