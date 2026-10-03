# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Loading ``cpdocs.yml``.

The configuration tells cpdocs how to ask the project for its feature sets, how to build one
selected feature set, and which Git versions to document. Project structure remains owned by the
build system and is communicated through JSON manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONTRACT_VERSION = 3
DEFAULT_CONFIG = Path("docs/cpdocs.yml")
_CHECK_LEVELS = {"ignore", "warn", "fail"}


@dataclass(frozen=True)
class CpdocsConfig:
    config_file: Path
    project_root: Path
    feature_sets: str
    build: str
    versions: tuple[str, ...]
    index: Path | None
    copyright: str | None
    project_docs: str
    hide_cpp_namespaces: tuple[str, ...]
    hide_private_python: bool
    check_undocumented: str
    check_broken_references: str


def project_root_for(config_file: Path) -> Path:
    """Return the repository root for a configuration file."""

    parent = config_file.resolve().parent
    return parent.parent if parent.name == "docs" else parent


def _mapping(value: object, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeError(f"cpdocs.yml: {name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _strings(value: object, name: str, *, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise RuntimeError(f"cpdocs.yml: {name} must be a list of non-empty strings")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise RuntimeError(f"cpdocs.yml: {name} must not contain duplicates")
    return result



def _versions(value: object) -> tuple[str, ...]:
    versions = _strings(value, "versions", default=("main",))
    if not versions:
        raise RuntimeError("cpdocs.yml: versions must contain at least one version")
    return versions


def _choice(value: object, name: str, allowed: set[str], default: str) -> str:
    result = str(value if value is not None else default)
    if result not in allowed:
        raise RuntimeError(f"cpdocs.yml: {name} must be one of {', '.join(sorted(allowed))}")
    return result


def _command(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"cpdocs.yml: {name} must be a non-empty command string")
    return value.strip()


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
    unknown_build = sorted(set(build) - {"feature-sets", "build"})
    if unknown_build:
        raise RuntimeError(f"cpdocs.yml: unknown build keys: {', '.join(unknown_build)}")
    site = _mapping(raw.get("site"), "site")
    api = _mapping(raw.get("api"), "api")
    hide = _mapping(api.get("hide"), "api.hide")
    checks = _mapping(raw.get("checks"), "checks")

    index_value = site.get("index")
    index = (
        (root / str(index_value)).resolve() if index_value else root / "docs" / "api" / "index.md"
    )
    copyright_value = site.get("copyright")

    return CpdocsConfig(
        config_file=config_file,
        project_root=root,
        feature_sets=_command(build.get("feature-sets"), "build.feature-sets"),
        build=_command(build.get("build"), "build.build"),
        versions=_versions(raw.get("versions")),
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
