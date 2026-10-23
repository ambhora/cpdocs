# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Only the project's own source files are read and published."""

from __future__ import annotations

import json
import pathlib

import pytest

import conftest
import cpdocs.build
import cpdocs.contract
import cpdocs.filesystem
import cpdocs.languages.cpp.extract
import cpdocs.languages.python.extract

SECRET = "private sentinel 6f1d"


def _secret(tmp_path: pathlib.Path) -> pathlib.Path:
    secret = tmp_path / "home" / "credentials"
    secret.parent.mkdir()
    secret.write_text(SECRET, encoding="utf-8")
    return secret


def _unit(project: pathlib.Path, *, generated: bool) -> object:
    (project / "include").mkdir(exist_ok=True)
    manifest = project.parent / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cpdocs-manifest": 1,
                "units": [
                    {
                        "id": "core",
                        "language": "c",
                        "api": [{"path": str(project / "include")}],
                        "sources": [str(project / "src")],
                        "generated": generated,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return cpdocs.contract.read_manifest(manifest, source=project).units[0]


def test_readable_file_follows_links_only_inside_roots(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.c").write_text("int a;", encoding="utf-8")
    (root / "inside").symlink_to(root / "a.c")
    (root / "outside").symlink_to(_secret(tmp_path))
    (root / "dangling").symlink_to(tmp_path / "missing")
    assert cpdocs.filesystem.readable_file(root / "a.c", (root,))
    assert cpdocs.filesystem.readable_file(root / "inside", (root,))
    assert not cpdocs.filesystem.readable_file(root / "outside", (root,))
    assert not cpdocs.filesystem.readable_file(root / "dangling", (root,))
    assert not cpdocs.filesystem.readable_file(root, (root,))


def test_browsing_does_not_follow_links_out_of_the_project(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.c").write_text("int a;\n", encoding="utf-8")
    (project / "src" / "leak.c").symlink_to(_secret(tmp_path))

    files, _generated, _display = cpdocs.build._collect_browse_files(
        _unit(project, generated=False), project_root=project, tracked=None
    )
    assert "src/a.c" in files
    assert all(SECRET not in content for content in files.values())


def test_browsing_publishes_only_tracked_files_inside_git(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.c").write_text("int a;\n", encoding="utf-8")
    conftest.init_repository(project)
    (project / "src" / "local.env").write_text(SECRET, encoding="utf-8")

    tracked = cpdocs.filesystem.git_tracked_files(project)
    assert tracked is not None
    files, _generated, _display = cpdocs.build._collect_browse_files(
        _unit(project, generated=False), project_root=project, tracked=tracked
    )
    assert set(files) == {"src/a.c"}

    # Generated units are produced by the build and are never tracked.
    files, _generated, _display = cpdocs.build._collect_browse_files(
        _unit(project, generated=True), project_root=project, tracked=tracked
    )
    assert "src/local.env" in files

    conftest.git(project, "add", "src/local.env")
    files, _generated, _display = cpdocs.build._collect_browse_files(
        _unit(project, generated=False), project_root=project, tracked=cpdocs.filesystem.git_tracked_files(project)
    )
    assert "src/local.env" in files


def test_git_tracked_files_outside_git(tmp_path: pathlib.Path) -> None:
    assert cpdocs.filesystem.git_tracked_files(tmp_path) is None


def test_python_packages_do_not_follow_links_out_of_the_project(tmp_path: pathlib.Path) -> None:
    package = tmp_path / "project" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (package / "leak.py").symlink_to(_secret(tmp_path))
    graph = cpdocs.languages.python.extract.build_python_graph(
        project_root=package.parent, package_root=package, package="demo"
    )
    assert all(SECRET not in content for content in graph.sources.values())
    assert "demo.leak" not in {entity.qualified_name for entity in graph.entities.values()}


def test_public_headers_do_not_follow_links_out_of_the_project(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "project"
    include = project / "include"
    include.mkdir(parents=True)
    (project / "detail.h").write_text("int d;\n", encoding="utf-8")
    (include / "a.h").write_text("int a;\n", encoding="utf-8")
    (include / "detail.h").symlink_to(project / "detail.h")
    (include / "leak.h").symlink_to(_secret(tmp_path))

    headers = cpdocs.languages.cpp.extract._public_headers([include], project)
    assert headers == sorted([(include / "a.h").resolve(), (project / "detail.h").resolve()])


@pytest.mark.parametrize("name", ['a"b.h', "a\nb.h", "a\rb.h"])
def test_umbrella_refuses_header_names_that_break_the_directive(tmp_path: pathlib.Path, name: str) -> None:
    with pytest.raises(RuntimeError, match="quote or line break"):
        cpdocs.languages.cpp.extract._write_umbrella(tmp_path / "umbrella.cpp", [tmp_path / name])
