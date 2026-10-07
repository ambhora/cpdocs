# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cpdocs.clang_backend import extract_clang_graph
from cpdocs.contract import ParseOptions
from cpdocs.html_renderer import render_html_site
from cpdocs.model import (
    ApiAttribute,
    ApiEntity,
    ApiGraph,
    ApiParameter,
    ApiSignature,
    merge_graphs,
    stable_entity_id,
)
from cpdocs.python_backend import build_python_graph
from cpdocs.render import entity_document
from cpdocs.rust_backend import build_rust_graph


def test_cpp_semantic_profiles_merge_conditional_api(tmp_path: Path) -> None:
    clang = shutil.which("clang++") or shutil.which("clang")
    if clang is None:
        pytest.skip("Clang is required for the semantic API backend")

    include = tmp_path / "include"
    include.mkdir()
    (include / "dice.hpp").write_text(
        """#pragma once
#ifdef USE_CUDA
/// Active backend.
#define DICE_BACKEND \"cuda\"
namespace dice { struct cuda_view {}; void foo(cuda_view); [[nodiscard]] int backend_name(); }
#else
/// Active backend.
#define DICE_BACKEND \"cpu\"
namespace dice { struct cpu_view {}; void foo(cpu_view); [[nodiscard]] int backend_name(); }
#endif
class visible { public: void yes(); private: void no(); };
""",
        encoding="utf-8",
    )

    graphs = []
    for feature_set, defines in (("cpu", ()), ("cuda", ("USE_CUDA=1",))):
        graph = extract_clang_graph(
            project="dice",
            version="main",
            project_root=tmp_path,
            language="cpp",
            api_roots=[include],
            parse=ParseOptions(
                standard="c++20",
                include=(),
                system_include=(),
                define=defines,
                flags=(),
                compile_database=None,
            ),
            feature_set=feature_set,
            clang_executable=clang,
            work_directory=tmp_path / "work" / feature_set,
        )
        for entity in graph.entities.values():
            entity.feature_sets.append(feature_set)
        graphs.append((feature_set, graph))

    merged = merge_graphs(graphs, project="dice", version="main", language="cpp")
    foo = merged.entities[stable_entity_id("cpp", "function", "dice::foo")]
    assert {signature.compact for signature in foo.signatures} == {"(cpu_view)", "(cuda_view)"}
    assert set(foo.feature_sets) == {"cpu", "cuda"}
    backend_name = merged.entities[stable_entity_id("cpp", "function", "dice::backend_name")]
    assert backend_name.signatures[0].attributes == (
        ApiAttribute(name="nodiscard", spelling="[[nodiscard]]"),
    )
    assert stable_entity_id("cpp", "method", "visible::yes") in merged.entities
    assert stable_entity_id("cpp", "method", "visible::no") not in merged.entities

    macro = merged.entities[stable_entity_id("cpp", "macro", "DICE_BACKEND")]
    assert set(macro.feature_sets) == {"cpu", "cuda"}
    assert set(macro.properties) == {'"cpu"', '"cuda"'}
    assert macro.source is not None and macro.source.path == "dice.hpp"


def test_python_backend_uses_same_graph_model(tmp_path: Path) -> None:
    package = tmp_path / "src" / "dice"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        '"""Dice package."""\nfrom .core import Solver\n__all__ = ["Solver"]\n', encoding="utf-8"
    )
    (package / "core.py").write_text(
        """from typing import Protocol, overload

class Reader(Protocol):
    def read(self, path: str, /, *, binary: bool = False) -> bytes: ...

class Solver:
    def __init__(self, value: int):
        self.value = value

    @overload
    def solve(self, value: int) -> int: ...

    @overload
    def solve(self, value: float) -> float: ...
""",
        encoding="utf-8",
    )

    graph = build_python_graph(
        project_root=tmp_path,
        package_root=package,
        package="dice",
        version="main",
    )
    assert (
        graph.entities[stable_entity_id("python", "package", "dice")].documentation
        == "Dice package."
    )
    reader = graph.entities[stable_entity_id("python", "protocol", "dice.core.Reader")]
    assert reader.kind == "protocol"
    constructor = graph.entities[
        stable_entity_id("python", "constructor", "dice.core.Solver.__init__")
    ]
    assert constructor.signatures[0].parameters[0].type == "int"
    solve = graph.entities[stable_entity_id("python", "method", "dice.core.Solver.solve")]
    # The implicit ``self`` is not part of the documented signature.
    assert {signature.compact for signature in solve.signatures} == {"(int)", "(float)"}


def test_rustdoc_backend_normalizes_function_signature(tmp_path: Path) -> None:
    rustdoc = tmp_path / "rustdoc.json"
    rustdoc.write_text(
        json.dumps(
            {
                "index": {
                    "0": {
                        "name": "parse",
                        "visibility": "public",
                        "docs": "Parse a value.",
                        "inner": {
                            "function": {
                                "sig": {
                                    "inputs": [
                                        [
                                            "value",
                                            {
                                                "borrowed_ref": {
                                                    "lifetime": None,
                                                    "is_mutable": False,
                                                    "type": {"primitive": "str"},
                                                }
                                            },
                                        ]
                                    ],
                                    "output": {
                                        "resolved_path": {
                                            "name": "Result",
                                            "args": {
                                                "angle_bracketed": {
                                                    "args": [{"type": {"primitive": "u64"}}]
                                                }
                                            },
                                        }
                                    },
                                },
                                "header": {
                                    "is_const": False,
                                    "is_async": False,
                                    "is_unsafe": False,
                                    "abi": "Rust",
                                },
                            }
                        },
                    }
                },
                "paths": {"0": {"path": ["dice", "parse"]}},
            }
        ),
        encoding="utf-8",
    )
    graph = build_rust_graph(rustdoc_json=rustdoc, project="dice", project_root=tmp_path)
    entity = graph.entities[stable_entity_id("rust", "function", "dice::parse")]
    assert entity.signatures[0].compact == "(&str)"
    assert entity.signatures[0].returns == "Result<u64>"


def test_renderer_generates_standalone_code_oriented_html_site(tmp_path: Path) -> None:
    graph = ApiGraph(project="dice", version="main", language="cpp")
    namespace = ApiEntity(
        id=stable_entity_id("cpp", "namespace", "dice"),
        language="cpp",
        kind="namespace",
        name="dice",
        qualified_name="dice",
        documentation="Dice public API.",
    )
    function = ApiEntity(
        id=stable_entity_id("cpp", "function", "dice::foo"),
        language="cpp",
        kind="function",
        name="foo",
        qualified_name="dice::foo",
        parent=namespace.id,
        signatures=[
            ApiSignature(
                parameters=(ApiParameter("value", "int"),),
                returns="void",
                attributes=(ApiAttribute(name="nodiscard", spelling="[[nodiscard]]"),),
            ),
            ApiSignature(parameters=(ApiParameter("value", "float"),), returns="void"),
        ],
        documentation=(
            "Do work. See [testing guide](projectdocs:reference/testing/#fixtures) and "
            "@projectdocs{blog/}.\n\nCPDOCS-API-RELATES-TO: bar"
        ),
        feature_sets=["feature-set-001"],
    )
    nested_namespace = ApiEntity(
        id=stable_entity_id("cpp", "namespace", "dice::meta"),
        language="cpp",
        kind="namespace",
        name="meta",
        qualified_name="dice::meta",
        parent=namespace.id,
    )
    nested_function = ApiEntity(
        id=stable_entity_id("cpp", "function", "dice::meta::nested"),
        language="cpp",
        kind="function",
        name="nested",
        qualified_name="dice::meta::nested",
        parent=nested_namespace.id,
        signatures=[ApiSignature(returns="void")],
    )
    related = ApiEntity(
        id=stable_entity_id("cpp", "class", "dice::bar"),
        language="cpp",
        kind="class",
        name="bar",
        qualified_name="dice::bar",
        parent=namespace.id,
    )
    method = ApiEntity(
        id=stable_entity_id("cpp", "method", "dice::bar::run"),
        language="cpp",
        kind="method",
        name="run",
        qualified_name="dice::bar::run",
        parent=related.id,
        signatures=[ApiSignature(parameters=(ApiParameter("value", "int"),), returns="void")],
    )
    package_info = ApiEntity(
        id=stable_entity_id("cpp", "struct", "dice::package_info"),
        language="cpp",
        kind="struct",
        name="package_info",
        qualified_name="dice::package_info",
        parent=namespace.id,
    )
    package = ApiEntity(
        id=stable_entity_id("cpp", "function", "dice::package"),
        language="cpp",
        kind="function",
        name="package",
        qualified_name="dice::package",
        parent=namespace.id,
        signatures=[ApiSignature(returns="package_info")],
    )
    macro = ApiEntity(
        id=stable_entity_id("cpp", "macro", "DICE_TEST"),
        language="cpp",
        kind="macro",
        name="DICE_TEST",
        qualified_name="DICE_TEST",
    )
    graph.add(namespace)
    graph.add(nested_namespace)
    graph.add(nested_function)
    graph.add(function)
    graph.add(related)
    graph.add(method)
    graph.add(package_info)
    graph.add(package)
    graph.add(macro)
    graph.sources["dice/version.hpp"] = "#pragma once\nnamespace dice { namespace meta {} }\n"
    graph.feature_sets["feature-set-001"] = {"features": ["cpu"], "selection": {"features": ["cpu"]}}
    graph.metadata = {
        "units": [{"id": "dice", "language": "cpp"}],
        "generator": "test",
    }
    graph.rebuild_children()

    site = tmp_path / "site"
    template = tmp_path / "api-docs"
    template.mkdir()
    (template / "index.md").write_text(
        "# API Documentation Home\n\n"
        "Reference for `{{ project }}` {{ version }}. See the "
        "[project blog](projectdocs:blog/).\n",
        encoding="utf-8",
    )
    render_html_site(
        graph,
        output_directory=site,
        project_docs_url="../../../../../",
        copyright_text="Copyright © dice developers",
        introduction_file=template / "index.md",
    )

    def html_page(document: Path) -> Path:
        if document.name == "index.md":
            return site / document.parent / "index.html"
        return site / document.with_suffix("") / "index.html"

    page = html_page(entity_document(function)).read_text(encoding="utf-8")
    assert '<article class="api-signature-card"' in page
    assert "foo(int)" in page
    assert page.count("nodiscard") >= 2
    assert "<span>nodiscard</span>" in page
    assert "Available in feature sets" in page
    assert "<code>cpu</code>" in page
    assert "<strong>Related:</strong>" in page
    assert "projectdocs:" not in page
    assert "reference/testing/#fixtures" in page
    assert ">blog</a>" in page
    assert 'class="language-cpp"' in page
    assert (site / "_symbols" / "dice" / "foo" / "index.html").is_file()
    class_page = html_page(entity_document(related)).read_text(encoding="utf-8")
    assert '<code class="language-cpp">' in class_page
    assert "Public Functions" in class_page
    assert 'id="member-method-run"' in class_page
    assert not html_page(entity_document(method)).is_file()
    method_alias = (site / "_symbols" / "dice" / "bar" / "run" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "#member-method-run" in method_alias
    package_page = html_page(entity_document(package)).read_text(encoding="utf-8")
    assert 'class="cpdocs-api-signature-type"' in package_page
    assert "struct-package_info/" in package_page
    namespace_page = html_page(entity_document(namespace)).read_text(encoding="utf-8")
    assert "Namespace dice" in namespace_page
    assert '<section id="members"' in namespace_page
    assert "Public Functions" not in namespace_page
    assert "Defined in" not in namespace_page
    assert ">foo()</a>" in namespace_page
    assert ">nested()</a>" in namespace_page
    assert ">run</a>" not in namespace_page
    nested_namespace_page = html_page(entity_document(nested_namespace)).read_text(encoding="utf-8")
    assert "groups the public API declared in this scope" in nested_namespace_page
    source_page = (site / "_sources" / "dice" / "version.hpp" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'class="language-cpp"' in source_page
    assert "style=" in source_page or "cpdocs-syntax-keyword" in source_page
    home_page = (site / "index.html").read_text(encoding="utf-8")
    assert "projectdocs:" not in home_page
    assert 'href="../../../../../blog/"' in home_page
    assert "Reference for <code>dice</code> main." in home_page
    assert "API hierarchy" in home_page
    assert "File Hierarchy" in home_page
    assert "api-legend" in home_page
    assert "DICE_TEST" in home_page
    assert 'title="directory">D</span><span>dice</span>' in home_page
    assert ">version.hpp</a>" in home_page
    assert (site / "macros" / "index.html").is_file()
    feature_sets_page = (site / "feature-sets" / "index.html").read_text(encoding="utf-8")
    assert "Described by" in feature_sets_page
    assert "Feature sets have no names" in feature_sets_page
    assert "cpu" in feature_sets_page
    assert 'class="api-feature-set-list"' in feature_sets_page
    assert 'class="api-feature-set-row"' in feature_sets_page
    assert (site / "assets" / "cpdocs-api.css").is_file()
    assert (site / "assets" / "cpdocs-api.js").is_file()
    assert "api-outline-children" in home_page
    assert ">run</a>" not in home_page
    assert home_page.count(">foo()</a>") == 2
    assert page.count('class="api-signature-card"') == 2
    class_toc = class_page.split('<aside class="api-toc">', 1)[1]
    assert "run(int)" in class_toc
    css = (site / "assets" / "cpdocs-api.css").read_text(encoding="utf-8")
    assert "--api-sidebar-default: 20.5rem; --api-toc-default: 24rem;" in css
    assert "width: min(80%, 80rem)" in css
    assert "--api-tree-indent: 2.45rem" in css
    assert '.api-outline-toggle::before { content: "+"' in css
    assert "grid-template-columns: 1.45rem minmax(0, 1fr) auto auto" in css
    assert ".api-outline-language { min-width: 0; justify-self: end; overflow: hidden; }" in css
    assert "text-overflow: ellipsis" in css
    assert '<span class="api-outline-language"><span class="api-language-badge">C++</span></span>' in home_page
    assert "border: 1px solid var(--api-border)" in css
    assert '"dice::foo"' in (site / "symbols.json").read_text(encoding="utf-8")


def test_feature_set_page_shows_opaque_selection(tmp_path: Path) -> None:
    graph = ApiGraph(project="demo", version="main", language="cpp")
    graph.add(
        ApiEntity(
            id=stable_entity_id("cpp", "namespace", "demo"),
            language="cpp",
            kind="namespace",
            name="demo",
            qualified_name="demo",
            feature_sets=["feature-set-001", "feature-set-002"],
        )
    )
    graph.feature_sets["feature-set-001"] = {
        "features": ["base"],
        "selection": {"features": ["base"]},
    }
    graph.feature_sets["feature-set-002"] = {
        "features": ["base", "gpu"],
        "selection": {"features": ["base", "gpu"]},
    }
    graph.rebuild_children()
    render_html_site(
        graph, output_directory=tmp_path / "site", project_docs_url="../", copyright_text="c"
    )
    page = (tmp_path / "site" / "feature-sets" / "index.html").read_text(encoding="utf-8")
    assert "Feature Sets" in page
    assert "Feature sets have no names" in page
    assert "<code>base</code> <code>gpu</code>" in page
