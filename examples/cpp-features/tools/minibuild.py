# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""A deliberately tiny build system that answers cpdocs requests for this project.

It exists to show that the cpdocs contract is not tied to CMake: any build system that can read
the request and write the two manifests works. It encodes the same knowledge as CMakeLists.txt --
which features exist, which variants to document, and how a feature becomes a compile definition.

Usage (from cpdocs): python tools/minibuild.py <request.json>
"""

import json
import sys

FEATURES = {"PROJECT_FEATURES": ["mpi", "cuda"]}
DEFINES = {"mpi": "DEMO_HAVE_MPI=1", "cuda": "DEMO_HAVE_CUDA=1"}
VARIANTS = {"serial": [], "mpi": ["mpi"], "full": ["mpi", "cuda"]}
PRIMARY = "serial"


def describe() -> dict:
    return {
        "cpdocs-manifest": 1,
        "kind": "describe",
        "generator": "minibuild",
        "project": {"name": "demo-solver", "version": "1.2.0"},
        "features": {axis: {"values": values} for axis, values in FEATURES.items()},
        "units": [{"id": "demo", "language": "cpp"}],
        "variants": [
            {
                "name": name,
                "primary": name == PRIMARY,
                "features": {"PROJECT_FEATURES": selected},
                "commands": [["{python}", "tools/minibuild.py", "{request}"]],
            }
            for name, selected in VARIANTS.items()
        ],
    }


def variant(name: str) -> dict:
    selected = VARIANTS[name]
    return {
        "cpdocs-manifest": 1,
        "kind": "variant",
        "variant": name,
        "features": {"PROJECT_FEATURES": selected},
        "units": [
            {
                "id": "demo",
                "language": "cpp",
                "api": [{"path": "include"}],
                "parse": {
                    "standard": "c++20",
                    "include": ["include"],
                    "define": [DEFINES[feature] for feature in selected],
                },
            }
        ],
    }


def main(request_file: str) -> int:
    with open(request_file, encoding="utf-8") as stream:
        request = json.load(stream)
    if request["phase"] == "describe":
        manifest = describe()
    else:
        manifest = variant(request["variant"])
    with open(request["manifest"], "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
