# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""cpdocs writes only inside the directories it owns."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cpdocs.build import _collect_browse_files
from cpdocs.contract import read_manifest
from cpdocs.filesystem import contained_path, path_component
from cpdocs.model import ApiEntity, ApiGraph, relative_source_path
from cpdocs.rendering.html import render_html_site


def _render(graph: ApiGraph, output: Path) -> None:
    render_html_site(graph, output_directory=output, project_docs_url="../", copyright_text="c")


def _files_outside(root: Path, inside: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not path.is_relative_to(inside) and path.name == "index.html"
    ]


def test_contained_path_refuses_escapes(tmp_path: Path) -> None:
    assert contained_path(tmp_path, Path("a/b")) == tmp_path / "a" / "b"
    for relative in ("/etc/passwd", "a/../../b", "..", ""):
        with pytest.raises(RuntimeError):
            contained_path(tmp_path, Path(relative))
    (tmp_path / "link").symlink_to(tmp_path.parent)
    with pytest.raises(RuntimeError):
        contained_path(tmp_path, Path("link/escaped"))


def test_path_component_keeps_plain_names_and_neutralizes_the_rest() -> None:
    assert path_component("core") == "core"
    assert path_component("demo.solver-2") == "demo.solver-2"
    for value in ("../../escaped", "..", ".", "a/b", "acme::math", ""):
        component = path_component(value)
        assert "/" not in component and component not in {".", ".."} and component
    assert path_component("a/b") != path_component("a-b")


def test_files_outside_the_project_get_relative_logical_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "registry" / "lib.rs"
    external.parent.mkdir()
    external.write_text("fn x() {}\n", encoding="utf-8")
    logical = relative_source_path(external, project)
    assert logical.startswith("_external/") and logical.endswith("/lib.rs")
    assert str(tmp_path) not in logical


def test_absolute_logical_source_paths_cannot_escape(tmp_path: Path) -> None:
    output = tmp_path / "out" / "site"
    graph = ApiGraph(project="p", version="main", language="rust")
    graph.sources[str(tmp_path / "escaped" / "lib.rs")] = "fn x() {}\n"
    with pytest.raises(RuntimeError, match="refuses"):
        _render(graph, output)
    assert _files_outside(tmp_path, output) == []
    assert not (tmp_path / "escaped").exists()


def test_symbol_names_cannot_escape_through_aliases(tmp_path: Path) -> None:
    output = tmp_path / "out" / "site"
    graph = ApiGraph(project="p", version="main", language="cpp")
    graph.add(
        ApiEntity(
            id="cpp:struct:X",
            language="cpp",
            kind="struct",
            name="X",
            qualified_name='X<"/../../../../../escaped-symbol">',
        )
    )
    graph.add(
        ApiEntity(
            id="cpp:struct:Y", language="cpp", kind="struct", name="Y", qualified_name="ns::Y"
        )
    )
    graph.rebuild_children()
    _render(graph, output)
    assert _files_outside(tmp_path, output) == []
    assert (output / "_symbols" / "ns" / "Y" / "index.html").is_file()


def test_manifest_unit_ids_cannot_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "generated"
    external.mkdir()
    (external / "mod.f90").write_text("module m\nend module m\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cpdocs-manifest": 1,
                "units": [
                    {
                        "id": "../../../escaped",
                        "language": "fortran",
                        "modules": [str(external)],
                        "sources": [str(external)],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    unit = read_manifest(manifest, source=project).units[0]
    files, _generated, _display = _collect_browse_files(unit, project_root=project)
    assert all(".." not in Path(path).parts for path in files)

    graph = ApiGraph(project="p", version="main", language="fortran")
    graph.files.update(files)
    output = project / "build" / "cpdocs" / "current"
    _render(graph, output)
    assert _files_outside(tmp_path, output) == []
