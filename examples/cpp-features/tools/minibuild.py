# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
"""A deliberately tiny build system implementing the cpdocs JSON contract.

It exists to show that cpdocs is not tied to CMake. The first command writes all feature sets; the
second receives one ``feature-set.json`` and writes the concrete ``manifest.json``.
"""

import json
import sys

DEFINES = {"mpi": "DEMO_HAVE_MPI=1", "cuda": "DEMO_HAVE_CUDA=1"}
FEATURE_SETS = [[], ["mpi"], ["mpi", "cuda"]]


def feature_sets() -> dict:
    return {
        "cpdocs-feature-sets": 1,
        "generator": "minibuild",
        "project": {"name": "demo-solver", "version": "1.2.0"},
        "feature-sets": [{"features": selected} for selected in FEATURE_SETS],
    }


def build(feature_set_file: str) -> dict:
    with open(feature_set_file, encoding="utf-8") as stream:
        selected = json.load(stream)
    features = selected["features"]
    return {
        "cpdocs-manifest": 1,
        "units": [
            {
                "id": "demo",
                "language": "cpp",
                "api": [{"path": "include"}],
                "parse": {
                    "standard": "c++20",
                    "include": ["include"],
                    "define": [DEFINES[feature] for feature in features],
                },
            }
        ],
    }


def main(argv: list[str]) -> int:
    phase = argv[0]
    if phase == "feature-sets":
        result = feature_sets()
        output = argv[1]
    elif phase == "build":
        result = build(argv[1])
        output = argv[2]
    else:
        raise SystemExit(f"unknown phase: {phase}")
    with open(output, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
