# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The JSON boundary between cpdocs and a project's build system.

cpdocs only needs to enumerate concrete feature sets and build one selected feature set at a time.
Feature sets are unnamed concrete sets of project features.  The manifest produced for one build
separately describes the semantic language of each API unit and, where needed, the parser frontend
used to extract it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTRACT_VERSION = 1
LANGUAGES = ("c", "cpp", "cuda", "hip", "fortran", "python", "rust")
CLANG_LANGUAGES = {"c", "cpp", "cuda", "hip"}
PARSER_LANGUAGES = {"c", "cpp"}


class ContractError(RuntimeError):
    """A build-system output does not satisfy the cpdocs contract."""


@dataclass(frozen=True)
class FeatureSetDeclaration:
    """One unnamed concrete feature set returned by the build system.

    ``key`` is an internal cpdocs identifier used only for work directories and links.  It is never
    written back to the build system or shown as the name of the feature set.
    """

    key: str
    features: tuple[str, ...]
    selection: dict[str, Any]

    def to_json(self) -> dict[str, object]:
        # Preserve the exact build-system-owned selection object, only adding the protocol marker.
        return {**self.selection, "cpdocs-feature-set": CONTRACT_VERSION}


@dataclass(frozen=True)
class FeatureSets:
    project: str
    version: str
    feature_sets: tuple[FeatureSetDeclaration, ...]
    generator: str


def _feature_set_key(index: int) -> str:
    return f"feature-set-{index + 1:03d}"


def read_feature_sets(path: Path) -> FeatureSets:
    raw = _load_json(path, "feature-sets manifest")
    if raw.get("cpdocs-feature-sets") != CONTRACT_VERSION:
        raise ContractError(
            f"{path}: unsupported cpdocs-feature-sets {raw.get('cpdocs-feature-sets')!r}"
        )
    project = _mapping(raw.get("project"), "project", path)
    raw_sets = raw.get("feature-sets")
    if not isinstance(raw_sets, list) or not raw_sets:
        raise ContractError(f"{path}: feature-sets must be a non-empty list")

    declarations: list[FeatureSetDeclaration] = []
    identities: set[tuple[str, ...]] = set()
    for index, value in enumerate(raw_sets):
        where = f"feature-sets[{index}]"
        data = _mapping(value, where, path)
        features = _feature_tuple(data.get("features"), path, where)
        identity = tuple(sorted(features))
        if identity in identities:
            raise ContractError(f"{path}: feature-sets must not contain duplicate feature sets")
        identities.add(identity)
        declarations.append(
            FeatureSetDeclaration(
                key=_feature_set_key(index),
                features=features,
                selection=data,
            )
        )

    return FeatureSets(
        project=_string(project, "name", path, "project"),
        version=str(project.get("version") or ""),
        feature_sets=tuple(declarations),
        generator=str(raw.get("generator") or ""),
    )


def write_feature_set(path: Path, feature_set: FeatureSetDeclaration) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feature_set.to_json(), indent=2) + "\n", encoding="utf-8")


def read_feature_set(path: Path) -> FeatureSetDeclaration:
    raw = _load_json(path, "feature-set input")
    if raw.get("cpdocs-feature-set") != CONTRACT_VERSION:
        raise ContractError(
            f"{path}: unsupported cpdocs-feature-set {raw.get('cpdocs-feature-set')!r}"
        )
    selection = {key: value for key, value in raw.items() if key != "cpdocs-feature-set"}
    features = _feature_tuple(selection.get("features"), path, "feature set")
    return FeatureSetDeclaration(key="selected", features=features, selection=selection)


@dataclass(frozen=True)
class ApiRoot:
    path: Path
    generated: bool


@dataclass(frozen=True)
class ParseOptions:
    standard: str
    include: tuple[Path, ...]
    system_include: tuple[Path, ...]
    define: tuple[str, ...]
    flags: tuple[str, ...]
    compile_database: Path | None
    language: str = "cpp"


@dataclass(frozen=True)
class UnitManifest:
    id: str
    # Semantic API language shown to readers: c, cpp, cuda, hip, ...
    language: str | None
    api: tuple[ApiRoot, ...]
    # Semantic layout roots/files are used only for the source browser.  They do not expand the API
    # boundary: API extraction still uses ``api`` (and, for Fortran, module sources).
    headers: tuple[Path, ...]
    sources: tuple[Path, ...]
    modules: tuple[Path, ...]
    executables: tuple[Path, ...]
    generated: bool
    # Parser/frontend details are independent of the semantic language.  CUDA and HIP headers, for
    # example, may be documented through the C++ frontend while remaining CUDA/HIP API units.
    parse: ParseOptions | None
    package: str | None
    rustdoc_json: Path | None


@dataclass(frozen=True)
class Manifest:
    units: tuple[UnitManifest, ...]


def read_manifest(path: Path, *, source: Path) -> Manifest:
    """Read the output of one build; relative paths are resolved against ``source``."""

    raw = _load_json(path, "manifest")
    if raw.get("cpdocs-manifest") != CONTRACT_VERSION:
        raise ContractError(f"{path}: unsupported cpdocs-manifest {raw.get('cpdocs-manifest')!r}")
    declarations = _units(raw.get("units"), path)
    units: list[UnitManifest] = []
    for declaration, value in zip(declarations, raw["units"], strict=True):
        where = f"unit {declaration.id!r}"
        data = _mapping(value, where, path)
        roots = data.get("api", [])
        if not isinstance(roots, list):
            raise ContractError(f"{path}: {where}: api must be a list")
        api: list[ApiRoot] = []
        for index, root in enumerate(roots):
            root_data = _mapping(root, f"{where}.api[{index}]", path)
            api.append(
                ApiRoot(
                    path=_path(_string(root_data, "path", path, where), source),
                    generated=bool(root_data.get("generated", False)),
                )
            )

        def paths(field: str) -> tuple[Path, ...]:
            return tuple(
                _path(item, source)
                for item in _string_tuple(data.get(field, []), f"{where}.{field}", path)
            )

        headers = paths("headers")
        sources = paths("sources")
        modules = paths("modules")
        executables = paths("executables")
        generated = bool(data.get("generated", False))

        parse: ParseOptions | None = None
        package: str | None = None
        rustdoc_json: Path | None = None
        if declaration.language in CLANG_LANGUAGES:
            if not api:
                raise ContractError(
                    f"{path}: {where}: a C/C++/CUDA/HIP unit needs at least one API root"
                )
            options = _mapping(data.get("parse", {}), f"{where}.parse", path)
            parser_language = str(
                options.get("language")
                or ("c" if declaration.language == "c" else "cpp")
            )
            if parser_language not in PARSER_LANGUAGES:
                raise ContractError(
                    f"{path}: {where}.parse.language must be one of "
                    + ", ".join(sorted(PARSER_LANGUAGES))
                )
            database = options.get("compile-database")
            parse = ParseOptions(
                standard=str(options.get("standard") or ""),
                include=tuple(
                    _path(item, source)
                    for item in _string_tuple(options.get("include", []), "include", path)
                ),
                system_include=tuple(
                    _path(item, source)
                    for item in _string_tuple(
                        options.get("system-include", []), "system-include", path
                    )
                ),
                define=_string_tuple(options.get("define", []), "define", path),
                flags=_string_tuple(options.get("flags", []), "flags", path),
                compile_database=_path(str(database), source) if database else None,
                language=parser_language,
            )
        elif declaration.language == "python":
            if len(api) != 1:
                raise ContractError(f"{path}: {where}: a Python unit needs exactly one API root")
            package = _string(data, "package", path, where)
        elif declaration.language == "rust":
            rustdoc_json = _path(_string(data, "rustdoc-json", path, where), source)
        elif declaration.language == "fortran":
            # Fortran modules carry their public declarations in source files rather than headers.
            # Build-system manifests expose module roots through the semantic ``modules`` field.
            if not api and not modules:
                raise ContractError(
                    f"{path}: {where}: a Fortran unit needs an API or modules root"
                )

        units.append(
            UnitManifest(
                id=declaration.id,
                language=declaration.language,
                api=tuple(api),
                headers=headers,
                sources=sources,
                modules=modules,
                executables=executables,
                generated=generated,
                parse=parse,
                package=package,
                rustdoc_json=rustdoc_json,
            )
        )

    return Manifest(units=tuple(units))


@dataclass(frozen=True)
class UnitDeclaration:
    id: str
    language: str | None


def _load_json(path: Path, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"the build system did not write the {what} {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read {what} {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ContractError(f"{path}: {what} must be a JSON object")
    return raw


def _mapping(value: object, name: str, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path}: {name} must be an object")
    return {str(key): item for key, item in value.items()}


def _string(data: dict[str, Any], key: str, path: Path, where: str = "") -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        prefix = f"{where}." if where else ""
        raise ContractError(f"{path}: {prefix}{key} must be a non-empty string")
    return value


def _string_tuple(value: object, name: str, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractError(f"{path}: {name} must be a list of strings")
    return tuple(value)


def _feature_tuple(value: object, path: Path, where: str) -> tuple[str, ...]:
    features = _string_tuple(value, f"{where}.features", path)
    if any(not feature for feature in features):
        raise ContractError(f"{path}: {where}.features must contain non-empty strings")
    if len(set(features)) != len(features):
        raise ContractError(f"{path}: {where}.features must not contain duplicates")
    return features


def _units(value: object, path: Path) -> tuple[UnitDeclaration, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{path}: units must be a non-empty list")
    units: list[UnitDeclaration] = []
    for index, item in enumerate(value):
        data = _mapping(item, f"units[{index}]", path)
        language_value = data.get("language")
        if language_value is None:
            language = None
        elif isinstance(language_value, str) and language_value in LANGUAGES:
            language = language_value
        else:
            raise ContractError(
                f"{path}: units[{index}].language must be null or one of {', '.join(LANGUAGES)}"
            )
        units.append(
            UnitDeclaration(id=_string(data, "id", path, f"units[{index}]"), language=language)
        )
    ids = [unit.id for unit in units]
    if len(set(ids)) != len(ids):
        raise ContractError(f"{path}: unit ids must be unique")
    return tuple(units)


def _path(value: str, source: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else source / path).resolve()
