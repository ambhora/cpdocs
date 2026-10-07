# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from cpdocs.config import load_config


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


MINIMAL = """contract: 3
build:
  feature-sets: make feature-sets OUTPUT={{output-file}}
  build: make build FEATURES={{feature-set}} OUTPUT={{output-file}}
"""


def test_minimal_config_has_documented_defaults(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path / "docs" / "cpdocs.yml", MINIMAL))
    assert config.project_root == tmp_path
    assert config.feature_sets == "make feature-sets OUTPUT={{output-file}}"
    assert config.build == "make build FEATURES={{feature-set}} OUTPUT={{output-file}}"
    assert config.versions == ("main",)
    assert config.index is None
    assert config.hide_private_python is True
    assert config.check_undocumented == "ignore"
    assert config.check_broken_references == "warn"


def test_index_defaults_to_docs_api(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "api" / "index.md", "# API\n")
    config = load_config(_write(tmp_path / "docs" / "cpdocs.yml", MINIMAL))
    assert config.index == tmp_path / "docs" / "api" / "index.md"


def test_config_outside_docs_belongs_to_its_directory(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path / "cpdocs.yml", MINIMAL))
    assert config.project_root == tmp_path


def test_full_config(tmp_path: Path) -> None:
    config = load_config(
        _write(
            tmp_path / "docs" / "cpdocs.yml",
            """contract: 3
build:
  feature-sets: cmake -S "{{source}}" -B "{{tmpdir}}" -DOUT="{{output-file}}"
  build: cmake -S "{{source}}" -B "{{tmpdir}}" -DFEATURES="{{feature-set}}" -DOUT="{{output-file}}"
versions: [main, v2.0.0, v1.0.0]
site:
  copyright: Copyright
  project-docs: https://example.org/
api:
  hide:
    cpp-namespaces: ["*::detail"]
    python-modules: none
checks:
  undocumented: fail
  broken-references: ignore
""",
        )
    )
    assert config.versions == ("main", "v2.0.0", "v1.0.0")
    assert config.hide_cpp_namespaces == ("*::detail",)
    assert config.hide_private_python is False
    assert config.check_undocumented == "fail"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("build:\n  feature-sets: make\n  build: make\n", "contract must be 3"),
        ("contract: 3\n", "build.feature-sets"),
        ("contract: 3\nbuild:\n  feature-sets: [make]\n  build: make\n", "command string"),
        ("contract: 3\nbuild:\n  feature-sets: make\n  build: make\n  manifest: make\n", "unknown build keys"),
        ("contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: {tags: all}\n", "versions must be a list"),
        ("contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: [main, main]\n", "duplicates"),
        ("contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: []\n", "at least one version"),
    ],
)
def test_invalid_configs_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        load_config(_write(tmp_path / "docs" / "cpdocs.yml", text))
