# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Every language the contract accepts has an extractor, presentation rules and a documented kind table."""

from __future__ import annotations

import importlib
import re

import pytest

from conftest import REPOSITORY
from cpdocs.contract import LANGUAGES
from cpdocs.languages import entity_kind, extractor_for, rendering_for
from cpdocs.languages.python.extract import target_python_version
from cpdocs.model import ApiEntity, ApiGraph


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_contract_language_is_supported(language: str) -> None:
    assert callable(extractor_for(language))
    assert rendering_for(language).separator


def test_unknown_languages_have_no_extractor() -> None:
    with pytest.raises(ValueError, match="unsupported API language"):
        extractor_for("cobol")


@pytest.mark.parametrize(
    ("configuration", "expected"),
    [({}, None), ({"cxx": {"standard": "17"}}, None), ({"python": {"version": "3.12"}}, (3, 12))],
)
def test_target_python_version(configuration: dict[str, object], expected: tuple[int, int] | None) -> None:
    assert target_python_version(configuration) == expected


def test_target_python_version_must_be_major_minor() -> None:
    with pytest.raises(RuntimeError, match="MAJOR.MINOR"):
        target_python_version({"python": {"version": "3"}})


ENTITY_KIND_PAGE = REPOSITORY / "docs" / "web" / "reference" / "entity-kinds.md"


@pytest.mark.parametrize("language", ["cpp", "fortran", "python", "rust"])
def test_entity_kind_tables_are_documented(language: str) -> None:
    module = importlib.import_module(f"cpdocs.languages.{language}.entities")
    table = module.__doc__.split("\n\n", 1)[1].strip()
    # The module docstring lists every declared kind, and the reference page repeats that table.
    listed = set(re.findall(r"``([a-z_]+)``", table.split("\n", 2)[2]))
    declared = {kind.name for kind in module.ENTITY_KINDS}
    assert {name for name in listed if name in declared} == declared
    assert table.replace("``", "`") in ENTITY_KIND_PAGE.read_text(encoding="utf-8")


def test_entities_of_undeclared_kinds_are_rejected() -> None:
    with pytest.raises(ValueError, match="python has no entity kind 'struct'"):
        ApiEntity(id="python:struct:x", language="python", kind="struct", name="x", qualified_name="x")
    with pytest.raises(ValueError, match="unsupported API language"):
        ApiEntity(id="cobol:x", language="cobol", kind="function", name="x", qualified_name="x")


def test_members_are_ordered_by_their_languages_kind_order() -> None:
    graph = ApiGraph(project="p", version="main", language="cpp")
    for kind, name in (("function", "a"), ("struct", "b"), ("namespace", "c"), ("macro", "d")):
        graph.add(ApiEntity(id=f"cpp:{kind}:{name}", language="cpp", kind=kind, name=name, qualified_name=name))
    assert [entity.kind for entity in graph.roots()] == ["namespace", "struct", "function", "macro"]
    assert entity_kind("cpp", "deduction_guide").label == "deduction guide"
