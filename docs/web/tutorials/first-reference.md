<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# A first API reference

This tutorial documents a small header-only C++ library built with CMake.

## The project

```text
demo/
  CMakeLists.txt
  include/demo/solver.hpp
  docs/
    cpdocs.yml
    api/index.md
```

`include/demo/solver.hpp` declares the API with ordinary documentation comments:

```cpp
#pragma once

/// A small solver.
namespace demo {

/// Settings of a solve.
struct settings {
    /// Maximum number of iterations.
    int iterations{100};
};

/// Solve on the calling thread.
double solve(settings const& options) noexcept;

} // namespace demo
```

## Let the build system describe the API

The build system owns the public API, the build variants, generated files and parser settings.
cpdocs asks it through two hooks: one writes `feature-sets.json`, the list of variants, and the other
writes one `manifest.json` per variant, naming its API headers and how to parse them.

A CMake project implements both hooks in its own `CMakeLists.txt`; cpdocs adds no CMake module. With
one variant this is a few lines:

```cmake
if(CPDOCS_FEATURE_SETS_OUTPUT)
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [{\"features\": []}]\n"
    "}\n")
endif()

if(CPDOCS_FEATURE_SET AND CPDOCS_MANIFEST_OUTPUT)
  file(WRITE "${CPDOCS_MANIFEST_OUTPUT}" "{\n"
    "  \"cpdocs-manifest\": 1,\n"
    "  \"units\": [{\n"
    "    \"id\": \"demo\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"parse\": {\"standard\": \"c++20\", \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"]}\n"
    "  }]\n"
    "}\n")
endif()
```

## Telling cpdocs how to ask

`docs/cpdocs.yml` names the two hooks, here two CMake invocations:

```yaml
contract: 3

build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SET="{{feature-set}}"
    -DCPDOCS_MANIFEST_OUTPUT="{{output-file}}"
```

The first hook runs once. cpdocs then writes the selected variant to `feature-set.json` and runs the
second hook once for each variant. The second hook always handles exactly one variant.

## Building

```console
$ cpdocs build
$ ls build/cpdocs/current
api  feature-sets  assets  index.html  ...
```

Open `build/cpdocs/current/index.html`. `docs/api/index.md` becomes the introduction of the
reference; `{{ project }}` and `{{ version }}` in it are replaced.

Next: [document build variants](../how-to/feature-sets.md) or [document several versions](../how-to/versions.md).
