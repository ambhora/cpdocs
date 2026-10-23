# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Shared fixtures: throw-away Git repositories and a scriptable fake build system."""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys

import pytest

REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = REPOSITORY / "examples"

# Make Git-driven tests independent of the developer/CI Git configuration and
# guarantee that no test can open an editor, pager, signing prompt, or credential prompt.
os.environ.update(
    {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "tag.gpgSign",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_EDITOR": "true",
        "GIT_SEQUENCE_EDITOR": "true",
        "GIT_PAGER": "cat",
        "MANPAGER": "cat",
        "PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
    }
)


def git(project: pathlib.Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=project, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return result.stdout


def init_repository(project: pathlib.Path) -> None:
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


def copy_example(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    project = tmp_path / name
    shutil.copytree(EXAMPLES / name, project, ignore=shutil.ignore_patterns("build"))
    return project


def fixture_text(name: str) -> str:
    """Load a self-contained fixture from test/share, never from runtime package assets."""
    return (pathlib.Path(__file__).parent / "share" / name).read_text(encoding="utf-8")


# A tiny build-system provider used by orchestration tests.
FAKE_BUILD = fixture_text("fake-build.py")


def fake_project(root: pathlib.Path, *, feature_sets: list[list[str]] | None = None, config: str = "") -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text(
        '"""A package."""\n\n\ndef answer() -> int:\n    """Return 42."""\n    return 42\n', encoding="utf-8"
    )
    (root / "fake_build.py").write_text(FAKE_BUILD, encoding="utf-8")
    spec: dict[str, object] = {"name": "fake", "feature_sets": feature_sets or [[]]}
    (root / "fake-build.json").write_text(json.dumps(spec), encoding="utf-8")
    (root / "docs").mkdir()
    python = shlex.quote(sys.executable)
    (root / "docs" / "cpdocs.yml").write_text(
        "contract: 3\n"
        "build:\n"
        f'  feature-sets: >\n    {python} fake_build.py feature-sets "{{{{output-file}}}}"\n'
        f'  build: >\n    {python} fake_build.py build "{{{{feature-set}}}}" "{{{{output-file}}}}"\n' + config,
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    return root
