# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Names and prose taken from documented sources never become markup or executable links."""

from __future__ import annotations

import json
import pathlib

import pytest

import conftest
import cpdocs.contract
import cpdocs.languages.python.extract
import cpdocs.rendering.html


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        " JaVaScRiPt:alert(1)",
        "java\tscript:alert(1)",
        "java\nscript:alert(1)",
        "\x01javascript:alert(1)",
        "javascript:alert(1)\x7f",
        "data:text/html,x",
        "vbscript:x",
        "file:///etc/passwd",
        "",
    ],
)
def test_executable_and_unknown_destinations_are_refused(href: str) -> None:
    assert cpdocs.rendering.html.safe_link_destination(href) is None
    rendered = cpdocs.rendering.html._inline_documentation(f"[label]({href})")
    assert "<a" not in rendered
    assert "label" in rendered


@pytest.mark.parametrize(
    "href",
    [
        "https://example.org/a?b=c#d",
        "http://example.org",
        "mailto:someone@example.org",
        "projectdocs:how-to/ci/",
        "../other/page/",
        "#anchor",
        "relative/page.html",
    ],
)
def test_ordinary_destinations_are_kept(href: str) -> None:
    assert cpdocs.rendering.html.safe_link_destination(href) == href
    assert "<a href=" in cpdocs.rendering.html._inline_documentation(f"[label]({href})")


def test_search_results_are_built_from_text_nodes() -> None:
    script = (conftest.REPOSITORY / "share" / "cpdocs" / "api" / "cpdocs-api.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script


def test_python_files_that_cannot_be_imported_are_not_api(tmp_path: pathlib.Path) -> None:
    package = tmp_path / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (package / "real.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (package / "<img src=x onerror=alert(1)>.py").write_text("x = 1\n", encoding="utf-8")
    (package / "not-a-module").mkdir()
    (package / "not-a-module" / "inner.py").write_text("y = 2\n", encoding="utf-8")

    graph = cpdocs.languages.python.extract.build_python_graph(
        project_root=tmp_path, package_root=package, package="demo"
    )

    names = {entity.qualified_name for entity in graph.entities.values()}
    assert "demo.real" in names
    assert not any("<" in name or "not-a-module" in name for name in names)
    # The files remain browsable source; only their API entities are withheld.
    assert "src/demo/<img src=x onerror=alert(1)>.py" in graph.sources


def test_python_package_names_must_be_identifiers(tmp_path: pathlib.Path) -> None:
    (tmp_path / "src").mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cpdocs-manifest": 1,
                "units": [{"id": "python", "language": "python", "package": "<b>demo</b>", "api": [{"path": "src"}]}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(cpdocs.contract.ContractError, match="dotted Python identifier"):
        cpdocs.contract.read_manifest(manifest, source=tmp_path)
