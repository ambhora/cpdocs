<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Command line

```text
cpdocs build [--config docs/cpdocs.yml] [--output build] [--label main] [--variants all|primary]
cpdocs versions [--config docs/cpdocs.yml] [--output build] [--tags SELECTOR]
cpdocs manifest python --request FILE --package NAME --source DIR
cpdocs cmake-module
```

`build` documents the working tree into `<output>/cpdocs/current`. `--label` is the version shown
in the reference.

`versions` documents the configured branches and tags into `<output>/cpdocs/versions`, one
directory per ref, with `versions.json` and alias redirects. `--tags` overrides
`versions.tags.select`.

`manifest python` answers a cpdocs request for a plain `pyproject.toml` project; see
[other build systems](../how-to/other-build-systems.md).

`cmake-module` prints the path of the CMake adapter.

Requests, manifests, build directories and build-system logs are kept in
`<output>/cpdocs/work/<ref>`. Clang is found as `clang++` or `clang` on `PATH`, or through
`CPDOCS_CLANG`.
