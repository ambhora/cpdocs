# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Static site resources must remain readable after cpdocs is installed as a package."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from cpdocs.build import _redirect_page
from cpdocs.resources import resource, shared_template, shared_text


def test_packaged_templates_and_assets_are_files() -> None:
    expected = (
        "layout.html",
        "redirect.html",
        "versions-redirect.html",
        "index.md",
        "namespace-description.html",
        "feature-sets-intro.html",
        "configuration-options-intro.html",
        "cpdocs-api.css",
        "cpdocs-api.js",
        "cpdocs-api-init.js",
    )
    for name in expected:
        assert resource("api", name).is_file(), name
        assert resource("api", name).read_bytes(), name
    assert "API Documentation Home" in shared_text("api/index.md")
    assert "${project}" in shared_text("api/layout.html")
    assert "${qualified_name}" in shared_text("api/namespace-description.html")
    assert "<code>demo</code>" in shared_template(
        "api/namespace-description.html"
    ).substitute(qualified_name="demo", kind="namespace")


def test_wheel_resource_mapping_and_isolated_loading(tmp_path: Path) -> None:
    """A wheel's shared directory remains readable outside the project tree."""
    repository = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
    mapping = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert mapping == {"share": "share"}

    # Reproduce the layout installed by the wheel without importing from
    # this source checkout or requiring the Hatch build backend in tests.
    site_packages = tmp_path / "site-packages"
    shutil.copytree(repository / "share", site_packages / "share")
    package = site_packages / "cpdocs"
    package.mkdir(parents=True)
    shutil.copy2(repository / "src" / "cpdocs" / "__init__.py", package / "__init__.py")
    shutil.copy2(repository / "src" / "cpdocs" / "resources.py", package / "resources.py")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cpdocs.resources import resource, shared_text; "
            "assert resource('api', 'cpdocs-api.css').is_file(); "
            "assert 'API Documentation Home' in shared_text('api/index.md')",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(site_packages)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_source_only_resource_lookup_from_elsewhere(tmp_path: Path) -> None:
    """A dev program using only PYTHONPATH=src can still find root-level share."""
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cpdocs.resources import shared_text; "
            "assert 'API Documentation Home' in shared_text('api/index.md')",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(repository / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

def test_version_redirect_uses_a_shared_template_and_escapes_html() -> None:
    text = _redirect_page("v1.2/")
    assert 'href="v1.2/"' in text
    assert 'content="0; url=v1.2/"' in text
    assert 'href="&quot;&gt;&lt;script&gt;"' in _redirect_page('"><script>')


def test_runtime_code_does_not_embed_large_static_strings() -> None:
    """Keep substantial resources in share; Python docstrings remain part of the API."""
    source_root = Path(__file__).resolve().parents[1] / "src" / "cpdocs"
    for filename in source_root.rglob("*.py"):
        tree = ast.parse(filename.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                assert len(node.value) < 250, (
                    f"{filename.relative_to(source_root)}:{node.lineno}: "
                    "move substantial static content to share/"
                )
