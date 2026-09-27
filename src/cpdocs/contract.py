# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The contract between cpdocs and a project's build system.

cpdocs never knows how a project is built. It hands the build system a *request* and reads back a
*manifest*. There are two phases:

``describe``
    The build system reports the project identity, its feature axes, the documentation units and
    the variants worth documenting. Every variant carries the commands that make it concrete.

``variant``
    The build system has been configured for exactly one variant and reports, per unit, which files
    form the public API and how they must be parsed.

The normative description lives in ``docs/web/reference/contract.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTRACT_VERSION = 1
LANGUAGES = ("c", "cpp", "python", "rust")


class ContractError(RuntimeError):
    """A request or manifest does not satisfy the cpdocs build-system contract."""


# --------------------------------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Request:
    phase: str
    ref: str
    ref_kind: str
    source: Path
    build: Path
    manifest: Path
    variant: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "cpdocs-request": CONTRACT_VERSION,
            "phase": self.phase,
            "ref": self.ref,
            "ref-kind": self.ref_kind,
            "variant": self.variant,
            "source": str(self.source),
            "build": str(self.build),
            "manifest": str(self.manifest),
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2) + "\n", encoding="utf-8")


def read_request(path: Path) -> Request:
    raw = _load_json(path, "request")
    if raw.get("cpdocs-request") != CONTRACT_VERSION:
        raise ContractError(f"{path}: unsupported cpdocs-request {raw.get('cpdocs-request')!r}")
    phase = _string(raw, "phase", path)
    if phase not in {"describe", "variant"}:
        raise ContractError(f"{path}: phase must be 'describe' or 'variant'")
    variant = raw.get("variant")
    if phase == "variant" and not isinstance(variant, str):
        raise ContractError(f"{path}: a variant request must name its variant")
    return Request(
        phase=phase,
        ref=_string(raw, "ref", path),
        ref_kind=_string(raw, "ref-kind", path),
        source=Path(_string(raw, "source", path)),
        build=Path(_string(raw, "build", path)),
        manifest=Path(_string(raw, "manifest", path)),
        variant=variant if isinstance(variant, str) else None,
    )


# --------------------------------------------------------------------------------------------------
# Describe manifest
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureAxis:
    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class UnitDeclaration:
    id: str
    language: str


@dataclass(frozen=True)
class VariantDeclaration:
    name: str
    primary: bool
    features: dict[str, tuple[str, ...]]
    commands: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class Description:
    project: str
    version: str
    features: tuple[FeatureAxis, ...]
    units: tuple[UnitDeclaration, ...]
    variants: tuple[VariantDeclaration, ...]
    generator: str

    @property
    def primary(self) -> VariantDeclaration:
        return next(variant for variant in self.variants if variant.primary)

    def variant(self, name: str) -> VariantDeclaration:
        for variant in self.variants:
            if variant.name == name:
                return variant
        raise ContractError(f"describe manifest has no variant {name!r}")


def read_description(path: Path) -> Description:
    raw = _load_json(path, "describe manifest")
    _check_header(raw, path, "describe")
    project = _mapping(raw.get("project"), "project", path)

    axes: list[FeatureAxis] = []
    for name, value in _mapping(raw.get("features", {}), "features", path).items():
        data = _mapping(value, f"features.{name}", path)
        values = _string_tuple(data.get("values"), f"features.{name}.values", path)
        if len(set(values)) != len(values):
            raise ContractError(f"{path}: features.{name}.values contains duplicates")
        axes.append(FeatureAxis(name=name, values=values))
    axis_values = {axis.name: set(axis.values) for axis in axes}

    units = _units(raw.get("units"), path)

    variants: list[VariantDeclaration] = []
    raw_variants = raw.get("variants")
    if not isinstance(raw_variants, list) or not raw_variants:
        raise ContractError(f"{path}: variants must be a non-empty list")
    for index, value in enumerate(raw_variants):
        where = f"variants[{index}]"
        data = _mapping(value, where, path)
        name = _string(data, "name", path, where)
        features = _features(data.get("features", {}), f"{where}.features", path)
        for axis, selected in features.items():
            if axis not in axis_values:
                raise ContractError(f"{path}: {where} uses undeclared feature axis {axis!r}")
            unknown = sorted(set(selected) - axis_values[axis])
            if unknown:
                raise ContractError(
                    f"{path}: {where} selects unknown {axis} values: {', '.join(unknown)}"
                )
        commands = data.get("commands")
        if not isinstance(commands, list):
            raise ContractError(f"{path}: {where}.commands must be a list of argv lists")
        variants.append(
            VariantDeclaration(
                name=name,
                primary=bool(data.get("primary", False)),
                features=features,
                commands=tuple(
                    _string_tuple(command, f"{where}.commands[{number}]", path)
                    for number, command in enumerate(commands)
                ),
            )
        )

    names = [variant.name for variant in variants]
    if len(set(names)) != len(names):
        raise ContractError(f"{path}: variant names must be unique")
    primaries = [variant.name for variant in variants if variant.primary]
    if len(primaries) != 1:
        raise ContractError(f"{path}: exactly one variant must be primary, found {len(primaries)}")

    return Description(
        project=_string(project, "name", path, "project"),
        version=str(project.get("version") or ""),
        features=tuple(axes),
        units=units,
        variants=tuple(variants),
        generator=str(raw.get("generator") or ""),
    )


# --------------------------------------------------------------------------------------------------
# Variant manifest
# --------------------------------------------------------------------------------------------------


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


@dataclass(frozen=True)
class UnitManifest:
    id: str
    language: str
    api: tuple[ApiRoot, ...]
    parse: ParseOptions | None
    package: str | None
    rustdoc_json: Path | None


@dataclass(frozen=True)
class VariantManifest:
    variant: str
    features: dict[str, tuple[str, ...]]
    units: tuple[UnitManifest, ...]


def read_variant_manifest(path: Path, *, source: Path) -> VariantManifest:
    """Read one variant manifest; relative paths are resolved against ``source``."""

    raw = _load_json(path, "variant manifest")
    _check_header(raw, path, "variant")
    units: list[UnitManifest] = []
    for declaration, value in zip(_units(raw.get("units"), path), raw["units"], strict=True):
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

        parse: ParseOptions | None = None
        package: str | None = None
        rustdoc_json: Path | None = None
        if declaration.language in {"c", "cpp"}:
            if not api:
                raise ContractError(f"{path}: {where}: a C/C++ unit needs at least one API root")
            options = _mapping(data.get("parse", {}), f"{where}.parse", path)
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
            )
        elif declaration.language == "python":
            if len(api) != 1:
                raise ContractError(f"{path}: {where}: a Python unit needs exactly one API root")
            package = _string(data, "package", path, where)
        elif declaration.language == "rust":
            rustdoc_json = _path(_string(data, "rustdoc-json", path, where), source)

        units.append(
            UnitManifest(
                id=declaration.id,
                language=declaration.language,
                api=tuple(api),
                parse=parse,
                package=package,
                rustdoc_json=rustdoc_json,
            )
        )

    return VariantManifest(
        variant=_string(raw, "variant", path),
        features=_features(raw.get("features", {}), "features", path),
        units=tuple(units),
    )


def check_variant(
    manifest: VariantManifest, *, description: Description, requested: str, path: Path
) -> None:
    """Reject a variant manifest that disagrees with what was requested and described."""

    if manifest.variant != requested:
        raise ContractError(
            f"{path}: build system answered for variant {manifest.variant!r}, "
            f"cpdocs requested {requested!r}"
        )
    declared = description.variant(requested)
    expected = {axis: tuple(sorted(values)) for axis, values in declared.features.items()}
    actual = {axis: tuple(sorted(values)) for axis, values in manifest.features.items()}
    for axis in {axis.name for axis in description.features}:
        expected.setdefault(axis, ())
        actual.setdefault(axis, ())
    if expected != actual:
        raise ContractError(
            f"{path}: variant {requested!r} was configured with features {actual}, "
            f"but the describe manifest declares {expected}"
        )
    described = [(unit.id, unit.language) for unit in description.units]
    reported = [(unit.id, unit.language) for unit in manifest.units]
    if sorted(described) != sorted(reported):
        raise ContractError(
            f"{path}: variant {requested!r} reports units {reported}, described units are "
            f"{described}"
        )


# --------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------


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


def _check_header(raw: dict[str, Any], path: Path, kind: str) -> None:
    if raw.get("cpdocs-manifest") != CONTRACT_VERSION:
        raise ContractError(f"{path}: unsupported cpdocs-manifest {raw.get('cpdocs-manifest')!r}")
    if raw.get("kind") != kind:
        raise ContractError(f"{path}: expected a {kind!r} manifest, found {raw.get('kind')!r}")


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


def _features(value: object, name: str, path: Path) -> dict[str, tuple[str, ...]]:
    data = _mapping(value, name, path)
    return {axis: _string_tuple(item, f"{name}.{axis}", path) for axis, item in data.items()}


def _units(value: object, path: Path) -> tuple[UnitDeclaration, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{path}: units must be a non-empty list")
    units: list[UnitDeclaration] = []
    for index, item in enumerate(value):
        data = _mapping(item, f"units[{index}]", path)
        language = _string(data, "language", path, f"units[{index}]")
        if language not in LANGUAGES:
            raise ContractError(
                f"{path}: units[{index}].language must be one of {', '.join(LANGUAGES)}"
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
