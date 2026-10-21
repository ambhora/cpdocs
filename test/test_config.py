# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import fixture_text
from cpdocs.build import _config_for_checkout
from cpdocs.config import SiteTheme, load_config


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
    assert config.theme == SiteTheme()


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
            fixture_text("complete-cpdocs.yml"),
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
        (
            "contract: 3\nbuild:\n  feature-sets: make\n  build: make\n  manifest: make\n",
            "unknown build keys",
        ),
        (
            "contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: {tags: all}\n",
            "versions must be a list",
        ),
        (
            "contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: [main, main]\n",
            "duplicates",
        ),
        (
            "contract: 3\nbuild:\n  feature-sets: make\n  build: make\nversions: []\n",
            "at least one version",
        ),
    ],
)
def test_invalid_configs_are_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        load_config(_write(tmp_path / "docs" / "cpdocs.yml", text))


THEMED = (
    MINIMAL
    + """site:
  theme:
    logo: share/icon.svg
    stylesheet: docs/api.css
    colors:
      light:
        selected: "#E6F0F2"
        accent: "#266C7C"
      dark:
        accent: "#65a9ba"
        on-accent: "#0d1f24"
"""
)


def _themed_project(root: Path, text: str = THEMED) -> Path:
    _write(root / "share" / "icon.svg", "<svg/>")
    _write(root / "share" / "favicon.png", "png")
    _write(root / "docs" / "api.css", ".api-brand { font-weight: 700; }\n")
    return _write(root / "docs" / "cpdocs.yml", text)


def test_theme_resolves_files_and_normalizes_colors(tmp_path: Path) -> None:
    config = load_config(_themed_project(tmp_path))
    assert config.theme == SiteTheme(
        logo=tmp_path / "share" / "icon.svg",
        # Without its own favicon the site uses the logo.
        favicon=tmp_path / "share" / "icon.svg",
        stylesheet=tmp_path / "docs" / "api.css",
        colors={
            "light": {"accent": "#266c7c", "selected": "#e6f0f2"},
            "dark": {"accent": "#65a9ba", "on-accent": "#0d1f24"},
        },
    )


def test_theme_favicon_can_differ_from_logo(tmp_path: Path) -> None:
    text = THEMED.replace(
        "    logo: share/icon.svg\n", "    logo: share/icon.svg\n    favicon: share/favicon.png\n"
    )
    config = load_config(_themed_project(tmp_path, text))
    assert config.theme.favicon == tmp_path / "share" / "favicon.png"


def test_theme_of_current_tree_applies_to_other_versions(tmp_path: Path) -> None:
    config = load_config(_themed_project(tmp_path / "current"))
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    assert _config_for_checkout(config, checkout).theme == config.theme


@pytest.mark.parametrize(
    ("theme", "message"),
    [
        ("    banner: share/icon.svg\n", "unknown site.theme keys: banner"),
        ("    logo: share/missing.svg\n", "site.theme.logo does not exist"),
        ("    logo: docs/api.css\n", "site.theme.logo must be one of"),
        ("    stylesheet: share/icon.svg\n", "site.theme.stylesheet must be one of .css"),
        ("    colors:\n      sepia: {}\n", "unknown site.theme.colors schemes: sepia"),
        ("    colors:\n      light:\n        link: '#ffffff'\n", "colours: link"),
        ("    colors:\n      light:\n        accent: #266c7c\n", "quoted in YAML"),
        ("    colors:\n      light:\n        accent: teal\n", "hexadecimal colour"),
    ],
)
def test_invalid_themes_are_rejected(tmp_path: Path, theme: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        load_config(_themed_project(tmp_path, MINIMAL + "site:\n  theme:\n" + theme))
