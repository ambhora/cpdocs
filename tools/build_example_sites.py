#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""Build the ProperDocs site of every example into ``<output>/<name>``.

The examples live in the cpdocs repository, so they are versioned with its branches and tags:
each site documents the example as it was at every configured ref. Run from a checkout with the
full history, as the documentation workflow does.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_REPOSITORY = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPOSITORY / "examples"


def build_site(example: Path, output: Path) -> None:
    shutil.rmtree(output, ignore_errors=True)
    result = subprocess.run(
        [sys.executable, "-m", "properdocs", "build", "--strict", "--site-dir", str(output)],
        cwd=example,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise SystemExit(f"properdocs build failed for {example.name}:\n{result.stdout}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=_REPOSITORY / "build" / "site" / "examples")
    parser.add_argument("--examples", type=Path, default=_EXAMPLES, help=argparse.SUPPRESS)
    parser.add_argument("names", nargs="*", help="examples to build (default: all)")
    arguments = parser.parse_args(argv)

    examples = arguments.examples.resolve()
    available = sorted(
        path.name for path in examples.iterdir() if (path / "properdocs.yml").is_file()
    )
    names = arguments.names or available
    unknown = sorted(set(names) - set(available))
    if unknown:
        parser.error(f"unknown examples: {', '.join(unknown)}")
    for name in names:
        build_site(examples / name, arguments.output.resolve() / name)
        print(f"{name}: {arguments.output / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
