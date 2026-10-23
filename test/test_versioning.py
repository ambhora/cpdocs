# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
from __future__ import annotations

import pathlib

import pytest

import conftest
import cpdocs.versioning


@pytest.fixture
def project(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    for variable in ("CPDOCS_CURRENT_BRANCH", "GITHUB_HEAD_REF", "CI_COMMIT_BRANCH", "GITHUB_REF_TYPE"):
        monkeypatch.delenv(variable, raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "readme.md").write_text("test\n", encoding="utf-8")
    conftest.init_repository(root)
    conftest.git(root, "tag", "v1.0.0")
    conftest.git(root, "tag", "v2.0.0")
    conftest.git(root, "branch", "release")
    return root


def test_versions_are_resolved_exactly_in_configured_order(project: pathlib.Path) -> None:
    refs = cpdocs.versioning.select_refs(project, ("v1.0.0", "main", "release", "v2.0.0"))
    assert [(ref.name, ref.kind) for ref in refs] == [
        ("v1.0.0", "tag"),
        ("main", "branch"),
        ("release", "branch"),
        ("v2.0.0", "tag"),
    ]
    assert refs[1].checkout is None
    assert refs[0].checkout == "refs/tags/v1.0.0"


def test_unknown_version_is_an_error(project: pathlib.Path) -> None:
    with pytest.raises(RuntimeError, match="v9.9.9"):
        cpdocs.versioning.select_refs(project, ("v9.9.9",))


def test_ci_clone_finds_remote_branch(project: pathlib.Path, tmp_path: pathlib.Path, monkeypatch) -> None:
    clone = tmp_path / "clone"
    conftest.git(tmp_path, "clone", "-q", str(project), str(clone))
    conftest.git(clone, "checkout", "-q", "--detach")
    monkeypatch.setenv("CI_COMMIT_BRANCH", "main")
    refs = cpdocs.versioning.select_refs(clone, ("main", "release"))
    assert [(ref.name, ref.checkout) for ref in refs] == [("main", None), ("release", "origin/release")]
