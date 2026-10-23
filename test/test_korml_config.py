# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""cpdocs.yml is read as Korml."""

from __future__ import annotations

from pathlib import Path

import korml
import pytest
import yaml

from conftest import REPOSITORY
from cpdocs.config import load_config

CONFIGURATIONS = sorted(
    path
    for pattern in ("docs/cpdocs*.yml", "examples/*/docs/cpdocs*.yml", "test/share/*cpdocs*.yml")
    for path in REPOSITORY.glob(pattern)
)

COMMANDS = 'build:\n  feature-sets: "true"\n  build: "true"\n'


def _as_text(value: object) -> object:
    """PyYAML's reading of a file, with its implicitly typed scalars spelled as Korml text.

    Block scalars compare exactly: Korml has no chomping indicators, so a configuration that used
    ``>-`` or ``|+`` would read differently under YAML and fail here.
    """

    if isinstance(value, dict):
        return {str(key): _as_text(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_as_text(child) for child in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | str):
        return str(value)
    raise AssertionError(f"scalar {value!r} has no unambiguous text spelling")


def _config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "docs" / "cpdocs.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_every_configuration_in_the_repository_is_covered() -> None:
    assert len(CONFIGURATIONS) >= 10


@pytest.mark.parametrize(
    "path", CONFIGURATIONS, ids=lambda path: path.relative_to(REPOSITORY).as_posix()
)
def test_korml_reads_every_configuration_as_yaml_did(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    (document,) = korml.loads(text, filename=str(path)).to_builtin()
    assert document == _as_text(yaml.safe_load(text))


def test_duplicate_keys_are_rejected_with_their_location(tmp_path: Path) -> None:
    path = _config(tmp_path, "contract: 3\n" + COMMANDS + "versions: [main]\nversions: [v1]\n")
    with pytest.raises(RuntimeError, match=r"duplicate mapping key 'versions'(.|\n)*:6:1"):
        load_config(path)


@pytest.mark.parametrize(
    "extra",
    [
        "versions: &v [main]\n",
        "versions: !!python/object:os.system [main]\n",
        "? versions\n: [main]\n",
    ],
)
def test_yaml_features_outside_korml_are_rejected(tmp_path: Path, extra: str) -> None:
    with pytest.raises(RuntimeError, match="cpdocs.yml: LexError"):
        load_config(_config(tmp_path, "contract: 3\n" + COMMANDS + extra))


def test_scalars_keep_their_spelling(tmp_path: Path) -> None:
    # YAML reads 1.10 as the float 1.1 and 3.0 as 3.0; Korml keeps the text that was written.
    config = load_config(_config(tmp_path, "contract: 3\n" + COMMANDS + "versions: [1.10, 3.0]\n"))
    assert config.versions == ("1.10", "3.0")


@pytest.mark.parametrize(("contract", "accepted"), [("3", True), ('"3"', True), ("4", False)])
def test_contract_is_compared_as_text(tmp_path: Path, contract: str, accepted: bool) -> None:
    path = _config(tmp_path, f"contract: {contract}\n" + COMMANDS)
    if accepted:
        load_config(path)
    else:
        with pytest.raises(RuntimeError, match="contract must be 3"):
            load_config(path)


def test_keyso_intervals_get_integer_bounds(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        "contract: 3\nlanguages:\n  cxx:\n    _nested:\n      standard:\n"
        "        _interval: {start: 17, stop: 23, step: 3}\n" + COMMANDS,
    )
    standards = [entry["cxx"]["standard"] for entry in load_config(path).language_configurations]
    assert standards == [17, 20, 23]


def test_keyso_interval_bounds_must_be_integers(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        "contract: 3\nlanguages:\n  cxx:\n    _nested:\n      standard:\n"
        "        _interval: {start: c++17, stop: 23}\n" + COMMANDS,
    )
    with pytest.raises(RuntimeError, match=r"_interval\.start must be an integer"):
        load_config(path)


def test_a_configuration_is_one_document(tmp_path: Path) -> None:
    path = _config(
        tmp_path,
        "%!korml version 1.0\n---\ncontract: 3\n" + COMMANDS + "...\n---\ncontract: 3\n...\n",
    )
    with pytest.raises(RuntimeError, match="single document"):
        load_config(path)


def test_an_empty_configuration_is_reported_as_missing_settings(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="contract must be 3"):
        load_config(_config(tmp_path, "# nothing yet\n"))
