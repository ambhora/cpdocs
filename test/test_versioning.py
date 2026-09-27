# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git, init_repository
from cpdocs.versioning import latest_tag, select_refs, select_tags


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for variable in (
        "CPDOCS_CURRENT_BRANCH",
        "GITHUB_HEAD_REF",
        "CI_COMMIT_BRANCH",
        "GITHUB_REF_TYPE",
    ):
        monkeypatch.delenv(variable, raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "readme.md").write_text("test\n", encoding="utf-8")
    init_repository(root)
    for tag in ("v0.8.0", "v0.9.0", "v0.10.0", "v0.11.0-rc.1", "v0.11.0", "nightly"):
        git(root, "tag", tag)
    git(root, "branch", "release/1.x")
    git(root, "branch", "release/2.x")
    return root


def test_tag_selectors(project: Path) -> None:
    assert select_tags(project, "all") == ["v0.11.0", "v0.11.0-rc.1", "v0.10.0", "v0.9.0", "v0.8.0"]
    assert select_tags(project, "latest:2") == ["v0.11.0", "v0.11.0-rc.1"]
    assert select_tags(project, "range:>=0.9,<0.11") == ["v0.11.0-rc.1", "v0.10.0", "v0.9.0"]
    assert select_tags(project, "refs:v0.8.0") == ["v0.8.0"]
    assert select_tags(project, "none") == []
    with pytest.raises(RuntimeError, match="unknown cpdocs Git tags"):
        select_tags(project, "refs:v9.9.9")


def test_branches_come_first_and_the_current_branch_is_the_working_tree(project: Path) -> None:
    refs = select_refs(project, branches=("main", "release/*"), tags="latest:1")
    assert [(ref.name, ref.kind) for ref in refs] == [
        ("main", "branch"),
        ("release/1.x", "branch"),
        ("release/2.x", "branch"),
        ("v0.11.0", "tag"),
    ]
    assert refs[0].checkout is None
    assert refs[1].checkout == "release/1.x"
    assert refs[3].checkout == "refs/tags/v0.11.0"


def test_missing_exact_branch_is_an_error(project: Path) -> None:
    with pytest.raises(RuntimeError, match="'develop' does not exist"):
        select_refs(project, branches=("develop",), tags="none")


def test_ci_clone_finds_branches_on_the_remote(project: Path, tmp_path: Path, monkeypatch) -> None:
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(project), str(clone))
    git(clone, "checkout", "-q", "--detach")
    monkeypatch.setenv("CI_COMMIT_BRANCH", "main")
    refs = select_refs(clone, branches=("main", "release/2.x"), tags="none")
    assert [(ref.name, ref.checkout) for ref in refs] == [
        ("main", None),
        ("release/2.x", "origin/release/2.x"),
    ]


def test_latest_tag() -> None:
    assert latest_tag(["v1.0", "v1.10", "v1.9", "nightly"]) == "v1.10"
    assert latest_tag(["nightly"]) is None
