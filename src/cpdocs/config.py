# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Loading ``cpdocs.yml``.

The configuration holds documentation and publishing policy only. Everything about the project
itself -- its name, features, variants, units and API files -- comes from the build system through
the manifests described in :mod:`cpdocs.contract`. ``cpdocs.yml`` therefore never names a feature or
a variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONTRACT_VERSION = 1
DEFAULT_CONFIG = Path("docs/cpdocs.yml")
_CHECK_LEVELS = {"ignore", "warn", "fail"}
_VARIANT_POLICIES = {"all", "primary"}


@dataclass(frozen=True)
class CpdocsConfig:
    config_file: Path
    project_root: Path
    describe: tuple[tuple[str, ...], ...]
    branches: tuple[str, ...]
    branch_variants: str
    tags: str
    tag_variants: str
    default_version: str
    aliases: dict[str, str]
    failure: str
    legacy: str
    index: Path | None
    copyright: str | None
    project_docs: str
    hide_cpp_namespaces: tuple[str, ...]
    hide_private_python: bool
    check_undocumented: str
    check_broken_references: str


def project_root_for(config_file: Path) -> Path:
    """Return the repository root for a configuration file.

    ``<root>/docs/cpdocs.yml`` belongs to ``<root>``; any other location belongs to the directory
    that contains the file. All paths in the configuration are relative to this root.
    """

    parent = config_file.resolve().parent
    return parent.parent if parent.name == "docs" else parent


def _mapping(value: object, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeError(f"cpdocs.yml: {name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _strings(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise RuntimeError(f"cpdocs.yml: {name} must be a list")
    return tuple(str(item) for item in value)


def _choice(value: object, name: str, allowed: set[str], default: str) -> str:
    result = str(value if value is not None else default)
    if result not in allowed:
        raise RuntimeError(f"cpdocs.yml: {name} must be one of {', '.join(sorted(allowed))}")
    return result


def _commands(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list) or not value:
        raise RuntimeError("cpdocs.yml: build.describe must be a non-empty list of commands")
    commands: list[tuple[str, ...]] = []
    for index, command in enumerate(value):
        if not isinstance(command, list) or not command:
            raise RuntimeError(f"cpdocs.yml: build.describe[{index}] must be a non-empty argv list")
        commands.append(tuple(str(item) for item in command))
    return tuple(commands)


def load_config(path: Path | str = DEFAULT_CONFIG) -> CpdocsConfig:
    config_file = Path(path).expanduser().resolve()
    if not config_file.is_file():
        raise RuntimeError(f"cpdocs configuration does not exist: {config_file}")
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError("cpdocs.yml: top level must be a mapping")
    if raw.get("contract") != CONTRACT_VERSION:
        raise RuntimeError(
            f"cpdocs.yml: contract must be {CONTRACT_VERSION}, found {raw.get('contract')!r}"
        )
    known = {"contract", "build", "versions", "site", "api", "checks"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise RuntimeError(f"cpdocs.yml: unknown top-level keys: {', '.join(unknown)}")

    root = project_root_for(config_file)
    build = _mapping(raw.get("build"), "build")
    versions = _mapping(raw.get("versions"), "versions")
    branches = _mapping(versions.get("branches"), "versions.branches")
    tags = _mapping(versions.get("tags"), "versions.tags")
    site = _mapping(raw.get("site"), "site")
    api = _mapping(raw.get("api"), "api")
    hide = _mapping(api.get("hide"), "api.hide")
    checks = _mapping(raw.get("checks"), "checks")

    index_value = site.get("index")
    index = (
        (root / str(index_value)).resolve() if index_value else root / "docs" / "api" / "index.md"
    )
    aliases = {
        str(key): str(value)
        for key, value in _mapping(versions.get("aliases"), "versions.aliases").items()
    }
    copyright_value = site.get("copyright")

    return CpdocsConfig(
        config_file=config_file,
        project_root=root,
        describe=_commands(build.get("describe")),
        branches=_strings(branches.get("include", ["main"]), "versions.branches.include"),
        branch_variants=_choice(
            branches.get("variants"), "versions.branches.variants", _VARIANT_POLICIES, "all"
        ),
        tags=str(tags.get("select", "all")).strip(),
        tag_variants=_choice(
            tags.get("variants"), "versions.tags.variants", _VARIANT_POLICIES, "all"
        ),
        default_version=str(versions.get("default") or "latest-tag"),
        aliases=aliases,
        failure=_choice(versions.get("failure"), "versions.failure", {"skip", "fail"}, "fail"),
        legacy=_choice(versions.get("legacy"), "versions.legacy", {"current", "skip"}, "current"),
        index=index if index.is_file() else None,
        copyright=str(copyright_value) if copyright_value is not None else None,
        project_docs=str(site.get("project-docs") or "auto"),
        hide_cpp_namespaces=_strings(hide.get("cpp-namespaces"), "api.hide.cpp-namespaces"),
        hide_private_python=_choice(
            hide.get("python-modules"), "api.hide.python-modules", {"private", "none"}, "private"
        )
        == "private",
        check_undocumented=_choice(
            checks.get("undocumented"), "checks.undocumented", _CHECK_LEVELS, "ignore"
        ),
        check_broken_references=_choice(
            checks.get("broken-references"), "checks.broken-references", _CHECK_LEVELS, "warn"
        ),
    )
