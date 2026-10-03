<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# demo-solver

A header-only solver whose API depends on `PROJECT_FEATURES`. The CMake build declares three feature sets: `serial`, `mpi` and `full`.

The main entry points of the API:

- @apidocs::demo::settings
- @apidocs::demo::solve
- @apidocs::demo::communicator
- @apidocs::demo::device

The [API reference](api.md) lists every published version.
