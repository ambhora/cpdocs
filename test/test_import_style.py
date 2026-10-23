# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""cpdocs code imports modules and names their members where it uses them.

``import pathlib`` and ``pathlib.Path(...)``, never ``from pathlib import Path``; ``import
cpdocs.model`` and ``cpdocs.model.ApiGraph``, never ``from .model import ApiGraph``. Only
``from __future__ import ...`` remains, because it is not an import of a module.

Ruff has no rule for this: TID252 rejects relative imports, which this test also covers, and
ICN003 rejects member imports only from modules listed by name. Hence this test.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import conftest

# The code of cpdocs, its tests and its helper scripts. Python sources that are documentation
# inputs, such as the example packages and test/share/python-*.py, are user code and keep their
# own style.
CODE = sorted(
    [
        *(conftest.REPOSITORY / "src").rglob("*.py"),
        *(conftest.REPOSITORY / "test").glob("*.py"),
        *(
            path
            for path in (conftest.REPOSITORY / "test" / "share").glob("*.py")
            if not path.name.startswith("python-")
        ),
        *(conftest.REPOSITORY / "examples").glob("*/tools/*.py"),
    ]
)


def _member_imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{path.relative_to(conftest.REPOSITORY)}:{node.lineno}: from {'.' * node.level}{node.module or ''} import ..."
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module != "__future__"
    ]


def test_the_import_style_covers_the_code() -> None:
    assert len(CODE) > 50


@pytest.mark.parametrize("path", CODE, ids=lambda path: path.relative_to(conftest.REPOSITORY).as_posix())
def test_code_imports_modules_not_members(path: pathlib.Path) -> None:
    assert _member_imports(path) == []
