# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""The checked-in examples, built through their real build systems."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import EXAMPLES, REPOSITORY, copy_example, git, init_repository, require
from cpdocs.build import build_current
from cpdocs.config import load_config
from cpdocs.model import stable_entity_id


def _build(tmp_path: Path, name: str, config: str = "docs/cpdocs.yml", output: str = "build"):
    project = copy_example(tmp_path, name)
    return project, build_current(load_config(project / config), output=project / output)


def _cmake_toolchain() -> None:
    require("cmake", "ninja", "clang++")


def test_python_example_needs_no_compiler(tmp_path: Path) -> None:
    _project, graph = _build(tmp_path, "python-basic")
    assert graph.project == "dice"
    assert stable_entity_id("python", "class", "dice.core.Die") in graph.entities
    assert graph.entities[stable_entity_id("python", "constant", "dice.SIDES")].documentation
    assert not any("_rng" in key for key in graph.entities)
    assert list(graph.feature_sets) == ["feature-set-001"]
    assert graph.feature_sets["feature-set-001"]["features"] == []


def test_cpp_features_example_documents_every_feature_set(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, graph = _build(tmp_path, "cpp-features")
    assert graph.project == "demo-solver"
    assert graph.metadata["feature_sets"][0]["features"] == []
    assert graph.metadata["feature_sets"][-1]["features"] == ["mpi", "cuda"]

    def feature_sets(kind: str, name: str) -> set[tuple[str, ...]]:
        entity = graph.entities[stable_entity_id("cpp", kind, name)]
        return {tuple(graph.feature_sets[key]["features"]) for key in entity.feature_sets}

    assert feature_sets("struct", "demo::settings") == {(), ("mpi",), ("mpi", "cuda")}
    assert feature_sets("struct", "demo::communicator") == {( "mpi",), ("mpi", "cuda")}
    assert feature_sets("struct", "demo::device") == {( "mpi", "cuda")}
    solve = graph.entities[stable_entity_id("cpp", "function", "demo::solve")]
    assert len(solve.signatures) == 3
    by_parameters = {
        signature.compact: (set(feature_sets), signature.documentation)
        for signature, feature_sets in zip(solve.signatures, solve.signature_feature_sets, strict=True)
    }
    def resolved(keys: set[str]) -> set[tuple[str, ...]]:
        return {tuple(graph.feature_sets[key]["features"]) for key in keys}

    assert resolved(by_parameters["(const settings &)"][0]) == {(), ("mpi",), ("mpi", "cuda")}
    assert (
        resolved(by_parameters["(const settings &, const communicator &)"][0]),
        by_parameters["(const settings &, const communicator &)"][1],
    ) == (
        {("mpi",), ("mpi", "cuda")},
        "Solve distributed over the ranks of a communicator.",
    )
    assert resolved(by_parameters["(const settings &, const device &)"][0]) == {("mpi", "cuda")}
    assert not any("detail" in key for key in graph.entities)

    feature_sets = json.loads(
        (
            project
            / "build"
            / "cpdocs"
            / "work"
            / "current"
            / "feature-sets"
            / "feature-sets.json"
        ).read_text()
    )
    selected = [item["features"] for item in feature_sets["feature-sets"]]
    assert selected == [[], ["mpi"], ["mpi", "cuda"]]


def test_a_different_build_system_gives_the_same_reference(tmp_path: Path) -> None:
    _cmake_toolchain()
    project = copy_example(tmp_path, "cpp-features")
    with_cmake = build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "a")
    with_minibuild = build_current(
        load_config(project / "docs" / "cpdocs-minibuild.yml"), output=project / "b"
    )
    assert with_cmake.entities == with_minibuild.entities
    assert [value["features"] for value in with_cmake.feature_sets.values()] == [
        value["features"] for value in with_minibuild.feature_sets.values()
    ]


def test_basic_cpp_example(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, graph = _build(tmp_path, "basic-cpp")
    assert graph.project == "cpdocs-basic-example"
    assert stable_entity_id("cpp", "struct", "acme::division_result") in graph.entities
    assert stable_entity_id("cpp", "macro", "ACME_API_VERSION_MAJOR") in graph.entities
    family = graph.entities[stable_entity_id("cpp", "function", "acme::to_string")]
    assert {signature.compact for signature in family.signatures} == {"(status)", "(bool)"}
    site = project / "build" / "cpdocs" / "current"
    assert (site / "api" / "acme" / "function-to_string" / "index.html").is_file()


def test_generated_headers_are_built_before_extraction(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, graph = _build(tmp_path, "generated-cpp")
    assert stable_entity_id("cpp", "struct", "acme::generated::configuration") in graph.entities
    assert graph.metadata["generated_sources"] == ["acme/generated.hpp"]
    page = (
        project
        / "build"
        / "cpdocs"
        / "current"
        / "_sources"
        / "acme"
        / "generated.hpp"
        / "index.html"
    )
    assert "Generated by the build" in page.read_text(encoding="utf-8")


def test_c_example(tmp_path: Path) -> None:
    _cmake_toolchain()
    _project, graph = _build(tmp_path, "c-basic")
    assert graph.language == "c"
    assert stable_entity_id("c", "function", "ring_push") in graph.entities
    ring = graph.entities[stable_entity_id("c", "struct", "ring")]
    assert ring.documentation == "A fixed-capacity ring buffer of bytes."
    # ``typedef struct ring {...} ring;`` documents the tag once.
    assert stable_entity_id("c", "type_alias", "ring") not in graph.entities


def test_mixed_example_merges_cpp_and_python_units(tmp_path: Path) -> None:
    _cmake_toolchain()
    _project, graph = _build(tmp_path, "mixed")
    assert graph.language == "mixed"
    assert [unit["id"] for unit in graph.metadata["units"]] == ["geom", "pygeom"]
    dot_many = graph.entities[stable_entity_id("cpp", "function", "geom::dot_many")]
    assert {tuple(graph.feature_sets[key]["features"]) for key in dot_many.feature_sets} == {
        ("simd",)
    }
    assert stable_entity_id("python", "function", "pygeom.dot") in graph.entities


def test_fortran_example_and_implementation_file_browser(tmp_path: Path) -> None:
    require("cmake", "ninja")
    project, graph = _build(tmp_path, "fortran-basic")
    assert graph.language == "fortran"
    module = graph.entities[stable_entity_id("fortran", "module", "geometry")]
    assert module.documentation == "Geometry primitives."
    vector = graph.entities[stable_entity_id("fortran", "derived_type", "geometry::vector3")]
    assert vector.documentation == "A three-dimensional vector."
    dot = graph.entities[stable_entity_id("fortran", "function", "geometry::dot")]
    assert dot.language == "fortran"
    assert dot.signatures[0].returns == "real"
    assert [parameter.type for parameter in dot.signatures[0].parameters] == [
        "type(vector3)",
        "type(vector3)",
    ]

    # Implementation-only files are browseable but do not create API entities.
    assert "lib/normalize.f90" in graph.files
    assert not any(entity.name == "normalize_impl" for entity in graph.entities.values())
    page = (
        project
        / "build"
        / "cpdocs"
        / "current"
        / "_sources"
        / "lib"
        / "normalize.f90"
        / "index.html"
    )
    assert page.is_file()
    assert "normalize_impl" in page.read_text(encoding="utf-8")
    dot_page = (
        project
        / "build"
        / "cpdocs"
        / "current"
        / "api"
        / "geometry"
        / "function-dot"
        / "index.html"
    ).read_text(encoding="utf-8")
    assert '<span class="api-language-badge">Fortran</span>' in dot_page


def test_cpp_file_hierarchy_includes_implementation_sources(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, graph = _build(tmp_path, "basic-cpp")
    assert "src/math.cpp" in graph.files
    implementation = (
        project
        / "build"
        / "cpdocs"
        / "current"
        / "_sources"
        / "src"
        / "math.cpp"
        / "index.html"
    )
    assert implementation.is_file()
    assert "File: src/math.cpp" in implementation.read_text(encoding="utf-8")


def test_examples_do_not_use_besa() -> None:
    for path in EXAMPLES.rglob("CMakeLists.txt"):
        text = path.read_text(encoding="utf-8")
        assert "find_package(besa" not in text
    for path in (REPOSITORY / "src").rglob("*.py"):
        assert "besa" not in path.read_text(encoding="utf-8").lower()


def test_properdocs_site_with_versions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _cmake_toolchain()
    properdocs = shutil.which("properdocs")
    if properdocs is None:
        pytest.skip("properdocs is required")
    for variable in (
        "CPDOCS_CURRENT_BRANCH",
        "GITHUB_HEAD_REF",
        "CI_COMMIT_BRANCH",
        "GITHUB_REF_TYPE",
    ):
        monkeypatch.delenv(variable, raising=False)
    project = copy_example(tmp_path, "cpp-features")
    init_repository(project)
    git(project, "tag", "1.0.0")
    config_file = project / "docs" / "cpdocs.yml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace(
            "versions: [main]", "versions: [1.0.0, main]"
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [properdocs, "build", "--strict"],
        cwd=project,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
    api = project / "build" / "site" / "reference" / "api"
    metadata = json.loads((api / "versions.json").read_text(encoding="utf-8"))
    assert metadata["default"] == "1.0.0"
    assert (api / "main" / "index.html").is_file()
    assert (api / "1.0.0" / "index.html").is_file()
    home = (project / "build" / "site" / "index.html").read_text(encoding="utf-8")
    # Semantic links point straight at the entity page, with no redirect in between.
    assert 'href="reference/api/1.0.0/api/demo/struct-settings/"' in home
    api_page = (project / "build" / "site" / "api" / "index.html").read_text(encoding="utf-8")
    assert 'href="../reference/api/main/"' in api_page
    assert 'href="../reference/api/1.0.0/"' in api_page


def test_broken_api_reference_fails_when_configured(tmp_path: Path) -> None:
    _cmake_toolchain()
    properdocs = shutil.which("properdocs")
    if properdocs is None:
        pytest.skip("properdocs is required")
    project = copy_example(tmp_path, "cpp-features")
    config = project / "docs" / "cpdocs.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "  undocumented: fail\n", "  undocumented: fail\n  broken-references: fail\n"
        ),
        encoding="utf-8",
    )
    (project / "docs" / "web" / "index.md").write_text(
        "See @apidocs::demo::nonexistent.\n", encoding="utf-8"
    )
    init_repository(project)
    result = subprocess.run(
        [properdocs, "build"],
        cwd=project,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode != 0
    assert "demo::nonexistent" in result.stdout


def test_root_properdocs_config_mounts_example_sites() -> None:
    import yaml

    configured = yaml.safe_load((REPOSITORY / "properdocs.yml").read_text(encoding="utf-8"))
    cpdocs_plugin = next(
        plugin["cpdocs"]
        for plugin in configured["plugins"]
        if isinstance(plugin, dict) and "cpdocs" in plugin
    )
    assert cpdocs_plugin["subsites"] == [
        "examples/basic-cpp",
        "examples/cpp-templates",
        "examples/cpp-features",
        "examples/generated-cpp",
        "examples/c-basic",
        "examples/mixed",
        "examples/fortran-basic",
        "examples/python-basic",
        "examples/rust-basic",
    ]
    assert not (REPOSITORY / "tools" / "build_example_sites.py").exists()


def test_templates_are_shown_as_written(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, graph = _build(tmp_path, "cpp-templates")

    def entity(kind: str, name: str):
        return graph.entities[stable_entity_id("cpp", kind, name)]

    assert entity("struct", "meta::vec").template == "template <typename T, std::size_t N>"
    assert entity("struct", "meta::vec<T, 0>").template == "template <typename T>"
    assert entity("struct", "meta::storage_traits<bool>").template == "template <>"
    assert "= 1" in entity("variable", "meta::storage_traits<bool>::bytes").properties
    assert entity("concept", "meta::addable").declaration.startswith(
        "template <typename T>\nconcept addable = requires(T a, T b) {"
    )
    assert entity("function", "meta::scale").signatures[0].template == (
        "template <typename T>\nrequires arithmetic<T>"
    )
    assert "std::enable_if_t" in entity("function", "meta::fsqrt").signatures[0].template
    assert entity("function", "meta::isqrt").signatures[0].returns.startswith("std::enable_if_t")
    assert entity("method", "meta::vec::operator[]").signatures[0].returns == "T &"
    guide = entity("deduction_guide", "meta::labelled::labelled")
    assert (
        guide.signatures[0].spelling
        == "template <typename T>\nlabelled(T, char const*) -> labelled<T>"
    )
    assert "`labelled<double>`" in guide.documentation
    assert "@tparam N Number of elements." in entity("struct", "meta::vec").documentation

    page = project / "build" / "cpdocs" / "current" / "api" / "meta" / "struct-vec" / "index.html"
    text = page.read_text(encoding="utf-8")
    assert "Specializations" in text and 'href="../struct-vec-t-0/"' in text


def test_introduction_license_header_is_not_rendered(tmp_path: Path) -> None:
    project, _graph = _build(tmp_path, "python-basic")
    home = (project / "build" / "cpdocs" / "current" / "index.html").read_text(encoding="utf-8")
    assert "SPDX" not in home
    assert "&lt;!--" not in home


def test_api_pages_work_on_small_screens_and_keep_the_theme(tmp_path: Path) -> None:
    project, _graph = _build(tmp_path, "python-basic")
    home = (project / "build" / "cpdocs" / "current" / "index.html").read_text(encoding="utf-8")
    head = home[: home.index("</head>")]
    assert "cpdocs-api-theme" in head  # the theme is chosen before the first paint
    assert 'class="api-short"' in home  # the project documentation link stays on phones
    css = (project / "build" / "cpdocs" / "current" / "assets" / "cpdocs-api.css").read_text()
    assert ".api-project-docs { display: none; }" not in css
    # Navigation between API pages is a plain page load; a cross-document view transition would
    # cross-fade two nearly identical pages, which reads as a blink.
    assert "@view-transition" not in css


def test_examples_are_versioned_from_the_enclosing_repository(tmp_path: Path, monkeypatch) -> None:
    for variable in (
        "CPDOCS_CURRENT_BRANCH",
        "GITHUB_HEAD_REF",
        "CI_COMMIT_BRANCH",
        "GITHUB_REF_TYPE",
    ):
        monkeypatch.delenv(variable, raising=False)
    from cpdocs.build import build_versions

    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "readme.md").write_text("before the example\n", encoding="utf-8")
    init_repository(repository)
    git(repository, "tag", "v0.1.0")

    example = repository / "examples" / "python-basic"
    shutil.copytree(EXAMPLES / "python-basic", example, ignore=shutil.ignore_patterns("build"))
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "add example")
    git(repository, "tag", "v0.2.0")
    (example / "src" / "dice" / "extra.py").write_text('"""Added in 0.3."""\n', encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "extend example")
    git(repository, "tag", "v0.3.0")

    config_file = example / "docs" / "cpdocs.yml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace(
            "versions: [main]", "versions: [v0.3.0, v0.2.0, main]"
        ),
        encoding="utf-8",
    )
    built = build_versions(load_config(config_file), output=example / "build")
    assert built == ["v0.3.0", "v0.2.0", "main"]

    def modules(ref: str) -> set[str]:
        path = example / "build" / "cpdocs" / "work" / ref / "render" / "api-graph.json"
        return set(json.loads(path.read_text(encoding="utf-8"))["entities"])

    assert "python:module:dice.extra" in modules("v0.3.0")
    assert "python:module:dice.extra" not in modules("v0.2.0")
    metadata = json.loads(
        (example / "build" / "cpdocs" / "versions" / "versions.json").read_text(encoding="utf-8")
    )
    assert metadata["default"] == "v0.3.0"


def test_specialization_rows_link_their_name(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, _graph = _build(tmp_path, "cpp-templates")
    page = project / "build" / "cpdocs" / "current" / "api" / "meta" / "struct-storage_traits"
    text = (page / "index.html").read_text(encoding="utf-8")
    section = text[
        text.index('id="specializations"') : text.index(
            "</section>", text.index('id="specializations"')
        )
    ]
    assert section.count("<a ") == 1  # no nested links
    assert '<a href="../struct-storage_traits-bool/"' in section
    assert ">storage_traits&lt;bool&gt;</a>" in section
    assert "Full specialization: booleans are stored as one byte." in section


def test_outline_collapses_on_small_screens(tmp_path: Path) -> None:
    project, _graph = _build(tmp_path, "python-basic")
    site = project / "build" / "cpdocs" / "current"
    page = next((site / "api").rglob("class-die/index.html")).read_text(encoding="utf-8")
    assert 'class="api-outline-panel-toggle"' in page
    assert 'aria-controls="api-outline-tree"' in page and 'id="api-outline-tree"' in page
    assert '<span class="api-outline-current">Die</span>' in page
    assert 'classList.add("js")' in page[: page.index("</head>")]
    css = (site / "assets" / "cpdocs-api.css").read_text(encoding="utf-8")
    assert ".js .api-sidebar:not(.is-open) .api-outline-root { display: none; }" in css


def test_urls_are_readable_and_collisions_stay_apart() -> None:
    from cpdocs.model import ApiEntity
    from cpdocs.rendering.common import _slug, assign_documents, entity_document

    assert _slug("storage_traits<bool>") == "storage_traits-bool"
    assert _slug("storage_traits<bool*>") == "storage_traits-bool-ptr"
    assert _slug("vec<T, 0>") == "vec-t-0"
    assert _slug("operator[]") == "operator-subscript"
    assert _slug("operator<<") == "operator-shl"
    assert _slug("operator<") == "operator-lt"
    assert _slug("operator bool") == "operator-bool"

    def struct(name: str) -> ApiEntity:
        return ApiEntity(
            id=f"cpp:struct:n::{name}",
            language="cpp",
            kind="struct",
            name=name,
            qualified_name=f"n::{name}",
        )

    plain, ref, spaced = struct("pair<int&>"), struct("pair<int>"), struct("pair< int >")
    assign_documents([plain, ref, spaced])
    try:
        assert entity_document(plain).as_posix() == "api/n/struct-pair-int-ref/index.md"
        # ``pair<int>`` and ``pair< int >`` share a readable path, so both get a digest.
        first, second = entity_document(ref), entity_document(spaced)
        assert first != second
        assert first.parent.name.startswith("struct-pair-int-")
        assert second.parent.name.startswith("struct-pair-int-")
    finally:
        assign_documents([])


def test_parameter_documentation_is_a_list(tmp_path: Path) -> None:
    _cmake_toolchain()
    project, _graph = _build(tmp_path, "cpp-templates")
    page = project / "build" / "cpdocs" / "current" / "api" / "meta" / "struct-vec" / "index.html"
    text = page.read_text(encoding="utf-8")
    assert '<p class="api-doc-field-title">Template parameters</p>' in text
    assert "<dt><code>T</code></dt><dd>Element type.</dd>" in text
    assert "<dt><code>N</code></dt><dd>Number of elements.</dd>" in text
    assert "**" not in text


def test_documentation_fields_and_strong_text() -> None:
    from cpdocs.rendering.html import _documentation_description

    rendered = _documentation_description(
        "Add **two** values.\n\n@param left Left operand.\n\n@param right Right operand."
        "\n\n@return Their sum.\n\n@throws std::overflow_error on overflow."
    )
    assert rendered.startswith("<p>Add <strong>two</strong> values.</p>")
    assert "<dt><code>left</code></dt><dd>Left operand.</dd>" in rendered
    assert '<p class="api-doc-field-title">Returns</p><p>Their sum.</p>' in rendered
    assert (
        '<p class="api-doc-field-title">Throws</p><p>std::overflow_error on overflow.</p>'
        in rendered
    )


def test_sidebars_are_resizable(tmp_path: Path) -> None:
    project, _graph = _build(tmp_path, "python-basic")
    site = project / "build" / "cpdocs" / "current"
    home = (site / "index.html").read_text(encoding="utf-8")
    assert 'class="api-resizer api-resizer-sidebar" data-resize="sidebar" role="separator"' in home
    assert 'class="api-resizer api-resizer-toc" data-resize="toc" role="separator"' in home
    # Saved widths are applied before the first paint, so the layout does not jump.
    assert "cpdocs-api-" in home[: home.index("</head>")]
    css = (site / "assets" / "cpdocs-api.css").read_text(encoding="utf-8")
    assert "grid-template-columns: var(--api-sidebar-width, var(--api-sidebar-default))" in css
    script = (site / "assets" / "cpdocs-api.js").read_text(encoding="utf-8")
    assert 'querySelectorAll(".api-resizer")' in script and "setPointerCapture" in script


def test_assets_are_versioned_so_browsers_do_not_keep_stale_styles(tmp_path: Path) -> None:
    import hashlib
    import re

    project, _graph = _build(tmp_path, "python-basic")
    site = project / "build" / "cpdocs" / "current"
    home = (site / "index.html").read_text(encoding="utf-8")
    css = (site / "assets" / "cpdocs-api.css").read_text(encoding="utf-8")
    script = (site / "assets" / "cpdocs-api.js").read_text(encoding="utf-8")
    stylesheet = re.search(r'href="assets/cpdocs-api\.css\?v=([0-9a-f]{10})"', home)
    loader = re.search(r'src="assets/cpdocs-api\.js\?v=([0-9a-f]{10})"', home)
    assert stylesheet and stylesheet.group(1) == hashlib.sha1(css.strip().encode()).hexdigest()[:10]
    assert loader and loader.group(1) == hashlib.sha1(script.strip().encode()).hexdigest()[:10]
