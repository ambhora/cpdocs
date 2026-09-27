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


def test_minimal_config_has_documented_defaults(tmp_path: Path) -> None:
    config = load_config(
        _write(
            tmp_path / "docs" / "cpdocs.yml", "contract: 1\nbuild:\n  describe: [[make, docs]]\n"
        )
    )
    assert config.project_root == tmp_path
    assert config.describe == (("make", "docs"),)
    assert config.branches == ("main",)
    assert config.tags == "all"
    assert config.branch_variants == config.tag_variants == "all"
    assert config.default_version == "latest-tag"
    assert config.failure == "fail"
    assert config.index is None
    assert config.hide_private_python is True
    assert config.check_undocumented == "ignore"
    assert config.check_broken_references == "warn"


def test_index_defaults_to_docs_api(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "api" / "index.md", "# API\n")
    config = load_config(
        _write(tmp_path / "docs" / "cpdocs.yml", "contract: 1\nbuild:\n  describe: [[make]]\n")
    )
    assert config.index == tmp_path / "docs" / "api" / "index.md"


def test_config_outside_docs_belongs_to_its_directory(tmp_path: Path) -> None:
    config = load_config(
        _write(tmp_path / "cpdocs.yml", "contract: 1\nbuild:\n  describe: [[make]]\n")
    )
    assert config.project_root == tmp_path


def test_full_config(tmp_path: Path) -> None:
    config = load_config(
        _write(
            tmp_path / "docs" / "cpdocs.yml",
            """contract: 1
build:
  describe:
    - [cmake, -S, "{source}", -B, "{build}"]
versions:
  branches: {include: [main, "release/*"], variants: primary}
  tags: {select: "range:>=1.0", variants: all}
  default: main
  aliases: {stable: latest-tag}
  failure: skip
  legacy: skip
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
    assert config.branches == ("main", "release/*")
    assert config.branch_variants == "primary"
    assert config.tags == "range:>=1.0"
    assert config.aliases == {"stable": "latest-tag"}
    assert (config.failure, config.legacy) == ("skip", "skip")
    assert config.hide_cpp_namespaces == ("*::detail",)
    assert config.hide_private_python is False
    assert config.check_undocumented == "fail"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("build:\n  describe: [[make]]\n", "contract must be 1"),
        ("contract: 1\n", "build.describe"),
        ("contract: 1\nbuild:\n  describe: [make]\n", "argv list"),
        ("contract: 1\nbuild:\n  describe: [[make]]\nfeatures: {}\n", "unknown top-level keys"),
        (
            "contract: 1\nbuild:\n  describe: [[make]]\nversions:\n  tags: {variants: some}\n",
            "versions.tags.variants",
        ),
    ],
)
def test_invalid_configs_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        load_config(_write(tmp_path / "docs" / "cpdocs.yml", text))
