# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Feature-set availability and semantic language are independent dimensions."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

from conftest import fixture_text, require
from cpdocs.build import build_current
from cpdocs.config import load_config
from cpdocs.model import stable_entity_id
from cpdocs.rendering.common import entity_document

PROVIDER = fixture_text("feature-set-provider.py")


def test_same_function_can_have_cpp_and_cuda_definitions(tmp_path: Path) -> None:
    require("clang++")
    project = tmp_path / "project"
    for backend, declaration in {
        "cpp": "int backend_value(int value) noexcept;",
        "cuda": "double backend_value(double value) noexcept;",
    }.items():
        include = project / "api" / backend / "demo"
        include.mkdir(parents=True, exist_ok=True)
        (include / "backend.hpp").write_text(
            "#pragma once\nnamespace demo {\n"
            f"/// {backend.upper()} definition.\n{declaration}\n"
            "}\n",
            encoding="utf-8",
        )

    (project / "provider.py").write_text(PROVIDER, encoding="utf-8")
    (project / "docs").mkdir()
    python = shlex.quote(sys.executable)
    (project / "docs" / "cpdocs.yml").write_text(
        "contract: 3\n"
        "build:\n"
        f'  feature-sets: {python} provider.py feature-sets "{{{{output-file}}}}"\n'
        f'  build: {python} provider.py build "{{{{feature-set}}}}" "{{{{output-file}}}}"\n',
        encoding="utf-8",
    )

    graph = build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")
    cpp = graph.entities[stable_entity_id("cpp", "function", "demo::backend_value")]
    cuda = graph.entities[stable_entity_id("cuda", "function", "demo::backend_value")]

    assert cpp.language == "cpp"
    assert cuda.language == "cuda"
    assert [(signature.returns, signature.compact) for signature in cpp.signatures] == [
        ("int", "(int)")
    ]
    assert [(signature.returns, signature.compact) for signature in cuda.signatures] == [
        ("double", "(double)")
    ]
    assert cpp.feature_sets == ["feature-set-001"]
    assert set(cuda.feature_sets) == {"feature-set-002", "feature-set-003"}
    assert graph.feature_sets["feature-set-001"]["features"] == ["host"]
    assert graph.feature_sets["feature-set-002"]["features"] == ["gpu"]
    assert graph.feature_sets["feature-set-003"]["features"] == ["gpu", "mpi"]

    site = project / "build" / "cpdocs" / "current"

    def html_page(entity) -> Path:
        document = entity_document(entity)
        if document.name == "index.md":
            return site / document.parent / "index.html"
        return site / document.with_suffix("") / "index.html"

    cpp_page = html_page(cpp).read_text(encoding="utf-8")
    cuda_page = html_page(cuda).read_text(encoding="utf-8")
    assert '<span class="api-language-badge">C++</span>' in cpp_page
    assert '<span class="api-language-badge">CUDA</span>' in cuda_page
    assert "Available in feature sets" in cuda_page
    assert "<code>gpu</code>" in cuda_page
    assert "<code>mpi</code>" in cuda_page
