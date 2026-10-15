# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import json, pathlib, sys
phase, standard, output = sys.argv[1:4]
if phase == "discover":
    value = {"cpdocs-feature-sets": 1, "generator": "test",
             "project": {"name": "demo", "version": "1"},
             "feature-sets": [{"features": []}, {"features": ["mpi"]}]}
else:
    selection = json.loads(pathlib.Path(sys.argv[4]).read_text())
    flags = ["MPI_ENABLED=1"] if "mpi" in selection["features"] else []
    value = {"cpdocs-manifest": 1, "units": [{
        "id": "demo", "language": "cpp", "api": [{"path": "include"}],
        "parse": {"language": "cpp", "standard": "c++" + standard, "define": flags}
    }]}
pathlib.Path(output).write_text(json.dumps(value), encoding="utf-8")
