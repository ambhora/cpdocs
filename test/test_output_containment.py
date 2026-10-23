# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""cpdocs writes and deletes only inside the directories it owns."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cpdocs.rendering.html as rendering
from cpdocs.build import Layout, _collect_browse_files
from cpdocs.contract import read_manifest
from cpdocs.filesystem import contained_path, path_component, remove_tree
from cpdocs.model import ApiEntity, ApiGraph, relative_source_path
from cpdocs.plugins.properdocs.core import mount_path, publish_api
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
    graph.add(ApiEntity(id="cpp:struct:Y", language="cpp", kind="struct", name="Y", qualified_name="ns::Y"))
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
    files, _generated, _display = _collect_browse_files(unit, project_root=project, tracked=None)
    assert all(".." not in Path(path).parts for path in files)

    graph = ApiGraph(project="p", version="main", language="fortran")
    graph.files.update(files)
    output = project / "build" / "cpdocs" / "current"
    _render(graph, output)
    assert _files_outside(tmp_path, output) == []


def test_render_refuses_to_replace_a_symbolic_link(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "sentinel").write_text("keep", encoding="utf-8")
    output = tmp_path / "out"
    output.symlink_to(victim, target_is_directory=True)

    graph = ApiGraph(project="p", version="main", language="none")
    with pytest.raises(RuntimeError, match="symbolic link"):
        _render(graph, output)
    assert (victim / "sentinel").read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in victim.iterdir()) == ["sentinel"]
    assert not any(".cpdocs-staging" in path.name for path in tmp_path.iterdir())


def test_failed_render_keeps_the_previous_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "site"
    graph = ApiGraph(project="p", version="main", language="none")
    _render(graph, output)
    previous = (output / "index.html").read_text(encoding="utf-8")

    def fail(*arguments: object, **keywords: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(rendering, "_render_site", fail)
    with pytest.raises(RuntimeError, match="render failed"):
        _render(graph, output)
    assert (output / "index.html").read_text(encoding="utf-8") == previous
    assert not any(".cpdocs-staging" in path.name for path in tmp_path.iterdir())


def test_remove_tree_refuses_links_below_the_owner(tmp_path: Path) -> None:
    victim = tmp_path / "victim"
    (victim / "versions").mkdir(parents=True)
    (victim / "versions" / "sentinel").write_text("keep", encoding="utf-8")
    output = tmp_path / "build"
    output.mkdir()
    (output / "cpdocs").symlink_to(victim, target_is_directory=True)

    layout = Layout.for_output(output)
    with pytest.raises(RuntimeError, match="symbolic link"):
        remove_tree(layout.versions, owner=layout.root.parent)
    assert (victim / "versions" / "sentinel").exists()


def test_output_roots_may_be_reached_through_links(tmp_path: Path) -> None:
    # Build directories on shared systems are often links to scratch space.
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    build = tmp_path / "build"
    build.symlink_to(scratch, target_is_directory=True)
    layout = Layout.for_output(build)
    _render(ApiGraph(project="p", version="main", language="none"), layout.current)
    assert (scratch / "cpdocs" / "current" / "index.html").is_file()
    _render(ApiGraph(project="p", version="main", language="none"), layout.current)
    assert (scratch / "cpdocs" / "current" / "index.html").is_file()


@pytest.mark.parametrize("mount", ["", "/", ".", "./", "..", "../victim", "a/../../b", "a//b"])
def test_mount_must_be_a_subdirectory_of_the_site(mount: str) -> None:
    with pytest.raises(ValueError, match="mount"):
        mount_path(mount)


def test_mount_keeps_ordinary_values() -> None:
    assert mount_path("/reference/api/").as_posix() == "reference/api"


def test_publish_api_cannot_delete_outside_the_site(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "sentinel").write_text("keep", encoding="utf-8")
    source = tmp_path / "api"
    source.mkdir()
    (source / "index.html").write_text("api", encoding="utf-8")

    with pytest.raises(ValueError):
        publish_api(source, site, "../victim")
    (site / "reference").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        publish_api(source, site, "reference/victim")
    assert (victim / "sentinel").read_text(encoding="utf-8") == "keep"

    published = publish_api(source, site, "docs/api")
    assert (published / "index.html").read_text(encoding="utf-8") == "api"
