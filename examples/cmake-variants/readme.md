<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs example: build variants in plain CMake

A header-only library with two variant axes: exactly one implementation, `host` or `gpu`, and MPI
optionally. `CMakeLists.txt` implements both cpdocs hooks in plain CMake: it lists the four variants
as the product of the two axes, and describes the selected variant. The GPU implementation adds a
unit documented as CUDA.

```console
cmake -S . -B build -DDEMO_FEATURES="gpu;mpi"   # an ordinary build of one variant
cpdocs build                                      # API reference of all variants in build/cpdocs/current
properdocs build                                  # project site with the versioned API, needs a Git repository
```
