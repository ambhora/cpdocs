# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import json
import sys

spec = json.load(open("fake-build.json"))
if sys.argv[1] == "feature-sets":
    manifest = {
        "cpdocs-feature-sets": 1,
        "generator": "fake",
        "project": {"name": spec["name"], "version": "1.0"},
        "feature-sets": [{"features": features} for features in spec["feature_sets"]],
    }
    output = sys.argv[2]
else:
    selected = json.load(open(sys.argv[2]))
    assert isinstance(selected["features"], list)
    manifest = {
        "cpdocs-manifest": 1,
        "units": [
            {"id": "pkg", "language": "python", "package": "pkg", "api": [{"path": "src/pkg"}]}
        ],
    }
    output = sys.argv[3]
json.dump(manifest, open(output, "w"))
