# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Placeholder values reach build commands as data, never as shell syntax."""

from __future__ import annotations

from pathlib import Path

import pytest

from cpdocs.providers.contract import _run_command, placeholder_variable


def _run(tmp_path: Path, command: str, values: dict[str, str]) -> str:
    output = tmp_path / "captured"
    _run_command(
        command + f' > "{output}"',
        source=tmp_path,
        values=values,
        allowed=set(values),
        name="build",
        log=tmp_path / "log.txt",
    )
    return output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "hostile",
    [
        "checkout$(touch SHELL_SENTINEL)",
        "checkout`touch SHELL_SENTINEL`",
        'checkout"; touch SHELL_SENTINEL; echo "',
        "checkout'; touch SHELL_SENTINEL; echo '",
    ],
)
def test_values_are_not_parsed_by_the_shell(tmp_path: Path, hostile: str) -> None:
    source = tmp_path / hostile
    source.mkdir()
    captured = _run(tmp_path, 'printf "%s" "{{source}}"', {"source": str(source)})
    assert captured == str(source)
    assert not (tmp_path / "SHELL_SENTINEL").exists()


def test_language_values_are_data_too(tmp_path: Path) -> None:
    captured = _run(
        tmp_path,
        'printf "%s|%s" "{{cxx.standard}}" "{{output-file}}"',
        {"cxx.standard": "$(touch SHELL_SENTINEL)", "output-file": "a b"},
    )
    assert captured == "$(touch SHELL_SENTINEL)|a b"
    assert not (tmp_path / "SHELL_SENTINEL").exists()


def test_commands_can_read_the_variables_directly(tmp_path: Path) -> None:
    captured = _run(tmp_path, 'printf "%s" "$CPDOCS_ARG_OUTPUT_FILE"', {"output-file": "x y"})
    assert captured == "x y"


def test_the_log_records_the_values(tmp_path: Path) -> None:
    _run(tmp_path, 'printf "%s" "{{source}}"', {"source": "a b"})
    log = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert "CPDOCS_ARG_SOURCE='a b'" in log
    assert '$ printf "%s" "${CPDOCS_ARG_SOURCE}"' in log


def test_placeholder_variable_names() -> None:
    assert placeholder_variable("source") == "CPDOCS_ARG_SOURCE"
    assert placeholder_variable("output-file") == "CPDOCS_ARG_OUTPUT_FILE"
    assert placeholder_variable("cxx.standard") == "CPDOCS_ARG_CXX_STANDARD"


def test_colliding_placeholders_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="both map to the environment variable"):
        _run(tmp_path, "true", {"output-file": "a", "output_file": "b"})
