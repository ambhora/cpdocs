# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Every language the contract accepts has an extractor and presentation rules."""

from __future__ import annotations

import pytest

from cpdocs.contract import LANGUAGES
from cpdocs.languages import extractor_for, rendering_for
from cpdocs.languages.python.extract import target_python_version


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
