# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Names and prose taken from documented sources never become markup or executable links."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import REPOSITORY
from cpdocs.contract import ContractError, read_manifest
from cpdocs.languages.python.extract import build_python_graph


def test_search_results_are_built_from_text_nodes() -> None:
    script = (REPOSITORY / "share" / "cpdocs" / "api" / "cpdocs-api.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script


def test_python_files_that_cannot_be_imported_are_not_api(tmp_path: Path) -> None:
    package = tmp_path / "src" / "demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (package / "real.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (package / "<img src=x onerror=alert(1)>.py").write_text("x = 1\n", encoding="utf-8")
    (package / "not-a-module").mkdir()
    (package / "not-a-module" / "inner.py").write_text("y = 2\n", encoding="utf-8")

    graph = build_python_graph(project_root=tmp_path, package_root=package, package="demo")

    names = {entity.qualified_name for entity in graph.entities.values()}
    assert "demo.real" in names
    assert not any("<" in name or "not-a-module" in name for name in names)
    # The files remain browsable source; only their API entities are withheld.
    assert "src/demo/<img src=x onerror=alert(1)>.py" in graph.sources


def test_python_package_names_must_be_identifiers(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "cpdocs-manifest": 1,
                "units": [
                    {
                        "id": "python",
                        "language": "python",
                        "package": "<b>demo</b>",
                        "api": [{"path": "src"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="dotted Python identifier"):
        read_manifest(manifest, source=tmp_path)
