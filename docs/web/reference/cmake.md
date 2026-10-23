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

A larger project can compute its variants in CMake as well: the
[cmake-variants example](../examples/index.md) lists a product of two variant axes and adds a CUDA
unit for one of them. A build framework can also implement the hooks once for all its projects; the
[BESA example](../examples/besa.md) shows one.

The boundary is the JSON contract, not CMake: cpdocs depends on no build system or framework.
