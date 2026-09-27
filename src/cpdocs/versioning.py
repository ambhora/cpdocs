# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Git-ref selection for cpdocs' versioned API site.

Branches are named explicitly (glob patterns allowed) and are always built. Tags are chosen by a
selector. Branch names are matched against local branches and, for CI clones that only carry the
checked-out branch locally, against remote-tracking branches as well.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

_RANGE_PART = re.compile(r"^(>=|<=|==|!=|>|<)\s*(.+)$")


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


def _versioned_tags(project_root: Path) -> list[tuple[Version, str]]:
    values: list[tuple[Version, str]] = []
    for tag in _git_ref_names(project_root, "tags"):
        try:
            parsed = Version(tag)
        except InvalidVersion:
            continue
        values.append((parsed, tag))
    return sorted(values, key=lambda item: (item[0], item[1]))


def _version_in_range(version_value: Version, expression: str) -> bool:
    comparators = [part.strip() for part in expression.split(",") if part.strip()]
    if not comparators:
        raise RuntimeError("cpdocs version range must contain at least one comparator")
    for comparator in comparators:
        match = _RANGE_PART.fullmatch(comparator)
        if match is None:
            raise RuntimeError(
                f"invalid cpdocs version range comparator {comparator!r}; use forms such as >=0.2,<0.6"
            )
        operator, raw_version = match.groups()
        try:
            boundary = Version(raw_version.strip())
        except InvalidVersion as error:
            raise RuntimeError(f"invalid cpdocs version {raw_version!r} in range") from error
        relation = {
            ">=": version_value >= boundary,
            "<=": version_value <= boundary,
            "==": version_value == boundary,
            "!=": version_value != boundary,
            ">": version_value > boundary,
            "<": version_value < boundary,
        }[operator]
        if not relation:
            return False
    return True


@dataclass(frozen=True)
class SelectedRef:
    """One version to build: its label, its kind and the Git object to check out.

    ``checkout`` is ``None`` when the label is the branch currently checked out, in which case the
    working tree itself is documented (uncommitted changes included).
    """

    name: str
    kind: str
    checkout: str | None


def select_tags(project_root: Path, value: str) -> list[str]:
    """Return tag names chosen by a selector, newest first."""

    value = value.strip()
    if value == "none":
        return []
    tags = _versioned_tags(project_root)
    if value == "all":
        return [tag for _version, tag in reversed(tags)]
    if value.startswith("latest:"):
        try:
            count = int(value.removeprefix("latest:").strip())
        except ValueError as error:
            raise RuntimeError(f"invalid cpdocs latest selector {value!r}") from error
        if count < 1:
            raise RuntimeError("cpdocs latest selector must request at least one version")
        return [tag for _version, tag in reversed(tags[-count:])]
    if value.startswith("range:"):
        expression = value.removeprefix("range:").strip()
        return [tag for parsed, tag in reversed(tags) if _version_in_range(parsed, expression)]
    if value.startswith("refs:"):
        requested = [
            item.strip() for item in value.removeprefix("refs:").split(",") if item.strip()
        ]
        if not requested:
            raise RuntimeError("cpdocs refs selector must contain at least one tag")
        known = set(_git_ref_names(project_root, "tags"))
        unknown = [name for name in requested if name not in known]
        if unknown:
            raise RuntimeError("unknown cpdocs Git tags: " + ", ".join(unknown))
        return requested
    raise RuntimeError(
        f"unsupported cpdocs tag selector {value!r}; expected all, none, latest:N, "
        "range:<comparators>, or refs:<tag,...>"
    )


def _branches(project_root: Path) -> dict[str, str]:
    """Map branch names to the ref that can be checked out, preferring local branches."""

    values: dict[str, str] = {}
    for remote_ref in _git_ref_names(project_root, "remotes"):
        remote, _, name = remote_ref.partition("/")
        if name and name != "HEAD":
            values.setdefault(name, f"{remote}/{name}")
    for name in _git_ref_names(project_root, "heads"):
        values[name] = name
    return values


def current_branch(project_root: Path) -> str | None:
    """Name of the checked-out branch, also in detached CI checkouts."""

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


def select_refs(project_root: Path, *, branches: tuple[str, ...], tags: str) -> list[SelectedRef]:
    """Select every version to build: the configured branches first, then the selected tags."""

    available = _branches(project_root)
    current = current_branch(project_root)
    selected: list[SelectedRef] = []
    seen: set[str] = set()
    for pattern in branches:
        if any(character in pattern for character in "*?["):
            matches = sorted(name for name in available if fnmatch.fnmatchcase(name, pattern))
        elif pattern in available or pattern == current:
            matches = [pattern]
        else:
            raise RuntimeError(
                f"configured branch {pattern!r} does not exist locally or on a remote; "
                "fetch it before building versions"
            )
        for name in matches:
            if name in seen:
                continue
            seen.add(name)
            checkout = None if name == current else available[name]
            selected.append(SelectedRef(name=name, kind="branch", checkout=checkout))
    for tag in select_tags(project_root, tags):
        if tag in seen:
            continue
        seen.add(tag)
        selected.append(SelectedRef(name=tag, kind="tag", checkout=f"refs/tags/{tag}"))
    return selected


def latest_tag(names: list[str]) -> str | None:
    """Return the highest semantic version among ``names``."""

    versions: list[tuple[Version, str]] = []
    for name in names:
        try:
            versions.append((Version(name), name))
        except InvalidVersion:
            continue
    return max(versions)[1] if versions else None
