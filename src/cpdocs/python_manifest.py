# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Contract provider for a plain ``pyproject.toml`` Python project."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .contract import CONTRACT_VERSION, read_feature_set


def _project(source: Path) -> dict[str, object]:
    path = source / "pyproject.toml"
    if not path.is_file():
        raise RuntimeError(f"cpdocs manifest python: {path} does not exist")
    project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
    if not isinstance(project, dict) or not project.get("name"):
        raise RuntimeError(f"cpdocs manifest python: {path} has no [project] name")
    return project


def write_feature_sets(source: Path, output: Path) -> Path:
    project = _project(source)
    manifest = {
        "cpdocs-feature-sets": CONTRACT_VERSION,
        "generator": "cpdocs manifest python",
        "project": {"name": str(project["name"]), "version": str(project.get("version") or "")},
        "feature-sets": [{"features": []}],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def write_manifest(
    source: Path,
    feature_set_file: Path,
    output: Path,
    *,
    package: str,
    package_source: str,
) -> Path:
    read_feature_set(feature_set_file)
    root = source / package_source
    if not root.is_dir():
        raise RuntimeError(f"cpdocs manifest python: package source {root} does not exist")
    manifest = {
        "cpdocs-manifest": CONTRACT_VERSION,
        "units": [
            {
                "id": package,
                "language": "python",
                "package": package,
                "api": [{"path": package_source}],
            }
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output
