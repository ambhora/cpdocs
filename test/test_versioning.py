# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git, init_repository
from cpdocs.versioning import select_refs


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for variable in ("CPDOCS_CURRENT_BRANCH", "GITHUB_HEAD_REF", "CI_COMMIT_BRANCH", "GITHUB_REF_TYPE"):
        monkeypatch.delenv(variable, raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "readme.md").write_text("test\n", encoding="utf-8")
    init_repository(root)
    git(root, "tag", "v1.0.0")
    git(root, "tag", "v2.0.0")
    git(root, "branch", "release")
    return root


def test_versions_are_resolved_exactly_in_configured_order(project: Path) -> None:
    refs = select_refs(project, ("v1.0.0", "main", "release", "v2.0.0"))
    assert [(ref.name, ref.kind) for ref in refs] == [
        ("v1.0.0", "tag"),
        ("main", "branch"),
        ("release", "branch"),
        ("v2.0.0", "tag"),
    ]
    assert refs[1].checkout is None
    assert refs[0].checkout == "refs/tags/v1.0.0"


def test_unknown_version_is_an_error(project: Path) -> None:
    with pytest.raises(RuntimeError, match="v9.9.9"):
        select_refs(project, ("v9.9.9",))


def test_ci_clone_finds_remote_branch(project: Path, tmp_path: Path, monkeypatch) -> None:
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(project), str(clone))
    git(clone, "checkout", "-q", "--detach")
    monkeypatch.setenv("CI_COMMIT_BRANCH", "main")
    refs = select_refs(clone, ("main", "release"))
    assert [(ref.name, ref.checkout) for ref in refs] == [
        ("main", None),
        ("release", "origin/release"),
    ]
