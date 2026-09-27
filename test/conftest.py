# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures: throw-away Git repositories and a scriptable fake build system."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[1]
EXAMPLES = REPOSITORY / "examples"


def git(project: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def init_repository(project: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("Git is required")
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "user.email", "cpdocs-test@example.invalid")
    git(project, "config", "user.name", "cpdocs Test")
    git(project, "add", "-A")
    git(project, "commit", "-q", "-m", "initial")


def require(*tools: str) -> None:
    for tool in tools:
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is required")


def copy_example(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    shutil.copytree(EXAMPLES / name, project, ignore=shutil.ignore_patterns("build"))
    return project


# A build system written for the tests: it answers requests from a JSON description, so each
# test can shape the manifests (including deliberately wrong ones) without CMake or Clang.
FAKE_BUILD = textwrap.dedent(
    """
    import json, sys
    request = json.load(open(sys.argv[1]))
    spec = json.load(open("fake-build.json"))
    if request["phase"] == "describe":
        manifest = {
            "cpdocs-manifest": 1, "kind": "describe", "generator": "fake",
            "project": {"name": spec["name"], "version": "1.0"},
            "features": {axis: {"values": values} for axis, values in spec["features"].items()},
            "units": [{"id": "pkg", "language": "python"}],
            "variants": [
                {"name": name, "primary": index == 0, "features": features,
                 "commands": [["{python}", "fake_build.py", "{request}"]]}
                for index, (name, features) in enumerate(spec["variants"].items())
            ],
        }
    else:
        name = request["variant"]
        manifest = {
            "cpdocs-manifest": 1, "kind": "variant", "variant": name,
            "features": spec.get("echo", spec["variants"])[name],
            "units": [{"id": "pkg", "language": "python", "package": "pkg",
                       "api": [{"path": "src/pkg"}]}],
        }
    json.dump(manifest, open(request["manifest"], "w"))
    """
)


def fake_project(
    root: Path,
    *,
    features: dict[str, list[str]] | None = None,
    variants: dict[str, dict[str, list[str]]] | None = None,
    echo: dict[str, dict[str, list[str]]] | None = None,
    config: str = "",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text(
        '"""A package."""\n\n\ndef answer() -> int:\n    """Return 42."""\n    return 42\n',
        encoding="utf-8",
    )
    (root / "fake_build.py").write_text(FAKE_BUILD, encoding="utf-8")
    spec: dict[str, object] = {
        "name": "fake",
        "features": features or {},
        "variants": variants or {"default": {}},
    }
    if echo is not None:
        spec["echo"] = echo
    (root / "fake-build.json").write_text(json.dumps(spec), encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "cpdocs.yml").write_text(
        'contract: 1\nbuild:\n  describe: [["{python}", fake_build.py, "{request}"]]\n' + config,
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    return root
