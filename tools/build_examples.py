#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build the API reference of every example into ``build/examples/<name>``.

Each example is copied first so that its own build directory stays clean. Requires cpdocs to be
installed (``uv sync``) and, for the C and C++ examples, CMake, Ninja and Clang.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from cpdocs.build import build_current
from cpdocs.config import load_config

_REPOSITORY = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=_REPOSITORY / "build" / "examples")
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    shutil.rmtree(output, ignore_errors=True)

    for example in sorted((_REPOSITORY / "examples").iterdir()):
        config = example / "docs" / "cpdocs.yml"
        if not config.is_file():
            continue
        with tempfile.TemporaryDirectory(prefix="cpdocs-example-") as temporary:
            project = Path(temporary) / example.name
            shutil.copytree(example, project, ignore=shutil.ignore_patterns("build"))
            build_current(load_config(project / "docs" / "cpdocs.yml"), output=project / "build")
            shutil.copytree(project / "build" / "cpdocs" / "current", output / example.name)
        print(f"{example.name}: {output / example.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
