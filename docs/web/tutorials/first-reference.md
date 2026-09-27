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

## Declaring the API in CMake

The build system decides what the API is. With CMake, `cpdocs_api` names the unit, the target
whose usage requirements are needed to parse it, and the directories that form the public API:

```cmake
cmake_minimum_required(VERSION 3.24)
project(demo VERSION 1.0.0 LANGUAGES CXX)

add_library(demo INTERFACE)
target_compile_features(demo INTERFACE cxx_std_20)
target_include_directories(demo INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

if(COMMAND cpdocs_api)
  cpdocs_api(UNIT demo LANGUAGE cpp TARGET demo API include)
endif()
```

The `if(COMMAND cpdocs_api)` guard keeps ordinary builds independent of cpdocs: the functions
exist only when cpdocs configures the project.

## Telling cpdocs how to ask

`docs/cpdocs.yml` holds the one command cpdocs runs to ask the build system for a description:

```yaml
contract: 1

build:
  describe:
    - [cmake, -S, "{source}", -B, "{build}", -G, Ninja,
       "-DCPDOCS_REQUEST={request}",
       "-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={cpdocs.cmake}"]
```

`{cpdocs.cmake}` expands to the CMake adapter shipped with cpdocs.

## Building

```console
$ cpdocs build
$ ls build/cpdocs/current
api  api-variants  assets  index.html  ...
```

Open `build/cpdocs/current/index.html`. `docs/api/index.md` becomes the introduction of the
reference; `{{ project }}` and `{{ version }}` in it are replaced.

Next: [document feature variants](../how-to/variants.md).
