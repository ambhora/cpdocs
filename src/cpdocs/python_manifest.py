# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""``cpdocs manifest python``: the contract answered for a plain ``pyproject.toml`` project.

A Python package built with a standard backend (hatchling, setuptools, ...) has nothing to
configure before its API can be read. This helper therefore plays the role of the build system in
the cpdocs contract: it answers the describe request with a single primary ``default`` variant, and
answers that variant's request with one Python unit.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .contract import CONTRACT_VERSION, Request, read_request


def _project(source: Path) -> dict[str, object]:
    path = source / "pyproject.toml"
    if not path.is_file():
        raise RuntimeError(f"cpdocs manifest python: {path} does not exist")
    project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
    if not isinstance(project, dict) or not project.get("name"):
        raise RuntimeError(f"cpdocs manifest python: {path} has no [project] name")
    return project


def _describe(request: Request, *, package: str, package_source: str) -> dict[str, object]:
    project = _project(request.source)
    command = [
        "{python}",
        "-m",
        "cpdocs",
        "manifest",
        "python",
        "--request",
        "{request}",
        "--package",
        package,
        "--source",
        package_source,
    ]
    return {
        "cpdocs-manifest": CONTRACT_VERSION,
        "kind": "describe",
        "generator": "cpdocs manifest python",
        "project": {"name": str(project["name"]), "version": str(project.get("version") or "")},
        "features": {},
        "units": [{"id": package, "language": "python"}],
        "variants": [{"name": "default", "primary": True, "features": {}, "commands": [command]}],
    }


def _variant(request: Request, *, package: str, package_source: str) -> dict[str, object]:
    root = request.source / package_source
    if not root.is_dir():
        raise RuntimeError(f"cpdocs manifest python: package source {root} does not exist")
    return {
        "cpdocs-manifest": CONTRACT_VERSION,
        "kind": "variant",
        "variant": request.variant,
        "features": {},
        "units": [
            {
                "id": package,
                "language": "python",
                "package": package,
                "api": [{"path": package_source}],
            }
        ],
    }


def write_manifest(request_file: Path, *, package: str, package_source: str) -> Path:
    request = read_request(request_file)
    if request.phase == "describe":
        manifest = _describe(request, package=package, package_source=package_source)
    else:
        manifest = _variant(request, package=package, package_source=package_source)
    request.manifest.parent.mkdir(parents=True, exist_ok=True)
    request.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return request.manifest
