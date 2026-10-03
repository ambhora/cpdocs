# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Resolve the explicit ``versions`` list from ``cpdocs.yml`` to Git refs."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _git_ref_names(project_root: Path, namespace: str) -> list[str]:
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", f"refs/{namespace}/"],
        cwd=project_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError("cpdocs version selection requires a readable Git repository")
    return [line for line in result.stdout.splitlines() if line]


@dataclass(frozen=True)
class SelectedRef:
    """One configured version and the Git object used to build it."""

    name: str
    kind: str
    checkout: str | None


def _branches(project_root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for remote_ref in _git_ref_names(project_root, "remotes"):
        remote, _, name = remote_ref.partition("/")
        if name and name != "HEAD":
            values.setdefault(name, f"{remote}/{name}")
    for name in _git_ref_names(project_root, "heads"):
        values[name] = name
    return values


def current_branch(project_root: Path) -> str | None:
    """Name of the checked-out branch, including common detached-CI environments."""

    for variable in ("CPDOCS_CURRENT_BRANCH", "GITHUB_HEAD_REF", "CI_COMMIT_BRANCH"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    if os.environ.get("GITHUB_REF_TYPE") == "branch" and os.environ.get("GITHUB_REF_NAME"):
        return os.environ["GITHUB_REF_NAME"]
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    value = result.stdout.strip()
    return value or None


def select_refs(project_root: Path, versions: tuple[str, ...]) -> list[SelectedRef]:
    """Resolve the configured version names exactly and preserve their order."""

    branches = _branches(project_root)
    tags = set(_git_ref_names(project_root, "tags"))
    current = current_branch(project_root)
    selected: list[SelectedRef] = []
    for name in versions:
        if name == current:
            selected.append(SelectedRef(name=name, kind="branch", checkout=None))
        elif name in branches:
            selected.append(SelectedRef(name=name, kind="branch", checkout=branches[name]))
        elif name in tags:
            selected.append(SelectedRef(name=name, kind="tag", checkout=f"refs/tags/{name}"))
        else:
            raise RuntimeError(
                f"configured version {name!r} is not a local/remote branch or tag; fetch it first"
            )
    return selected
