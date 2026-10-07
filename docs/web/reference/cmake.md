<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# CMake integration

cpdocs does not inject a CMake module and does not add CMake commands to a project. A CMake project
or a build framework used by that project implements the same two-file
[build-system contract](contract.md) as any other build system.

A project-local provider can be as small as ordinary `CMakeLists.txt` code which writes
`feature-sets.json` when `CPDOCS_FEATURE_SETS_OUTPUT` is set and writes `manifest.json` when
`CPDOCS_FEATURE_SET` and `CPDOCS_MANIFEST_OUTPUT` are set. The checked-in C and C++ examples use
this pattern directly, so a normal CMake configuration exercises exactly the same project logic as
cpdocs.

For example, a project with one feature set can expose discovery with:

```cmake
if(CPDOCS_FEATURE_SETS_OUTPUT)
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [{\"features\": []}]\n"
    "}\n")
endif()
```

and configure cpdocs with ordinary CMake invocations:

```yaml
build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SET="{{feature-set}}"
    -DCPDOCS_MANIFEST_OUTPUT="{{output-file}}"
```

A framework such as BESA can provide the contract natively. In that case the project does not need
cpdocs-specific provider code at all:

```yaml
build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DBESA_CPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DBESA_CPDOCS_FEATURE_SET="{{feature-set}}"
    -DBESA_CPDOCS_MANIFEST_OUTPUT="{{output-file}}"
    && cmake --build "{{tmpdir}}" --target besa.cpdocs
```

The important boundary is the JSON contract, not CMake itself. cpdocs remains independent of BESA
and of any other build framework.
