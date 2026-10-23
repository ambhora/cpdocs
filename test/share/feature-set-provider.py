# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import json
import pathlib
import sys

command = sys.argv[1]
if command == "feature-sets":
    output = pathlib.Path(sys.argv[2])
    value = {
        "cpdocs-feature-sets": 1,
        "generator": "test-provider",
        "project": {"name": "backend-api", "version": "1.0"},
        "feature-sets": [{"features": ["host"]}, {"features": ["gpu"]}, {"features": ["gpu", "mpi"]}],
    }
else:
    selected = json.load(open(sys.argv[2], encoding="utf-8"))
    features = selected["features"]
    gpu = "gpu" in features
    output = pathlib.Path(sys.argv[3])
    value = {
        "cpdocs-manifest": 1,
        "units": [
            {
                "id": "backend",
                "language": "cuda" if gpu else "cpp",
                "api": [{"path": "api/cuda" if gpu else "api/cpp"}],
                "parse": {"language": "cpp", "standard": "c++20"},
            }
        ],
    }
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(value), encoding="utf-8")
