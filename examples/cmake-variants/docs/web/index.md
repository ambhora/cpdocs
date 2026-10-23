<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# demo-variants

A plain CMake project with a variant space: exactly one implementation, `host` or `gpu`, and MPI
optionally. Its `CMakeLists.txt` lists the four variants for cpdocs and describes each of them, so
the reference shows which declarations exist in which variant.

- @apidocs::demo::scale exists in every variant; the overload taking a communicator only with `mpi`,
  and the CUDA overload taking a stream only with `gpu`.
- @apidocs::demo::stream exists only with `gpu`.

The [API reference](api.md) lists every published version.
