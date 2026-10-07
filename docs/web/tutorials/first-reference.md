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

The build system owns the public API, feature selection, generated files and parser settings. cpdocs
only asks it for `feature-sets.json` and then one `manifest.json` per selected feature set.

For CMake there is no injected cpdocs module. A project can provide those files directly from its
`CMakeLists.txt`, as the standalone examples do, or a build framework such as BESA can provide the
same contract natively. See [CMake integration](../reference/cmake.md) for the small provider pattern.

## Telling cpdocs how to ask

`docs/cpdocs.yml` contains only the two orchestration commands:

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

The first command runs once. cpdocs then writes one selected `feature-set.json` and runs the second
command once for each feature set. The build command never receives a list of feature sets.

## Building

```console
$ cpdocs build
$ ls build/cpdocs/current
api  feature-sets  assets  index.html  ...
```

Open `build/cpdocs/current/index.html`. `docs/api/index.md` becomes the introduction of the
reference; `{{ project }}` and `{{ version }}` in it are replaced.

Next: [document feature sets](../how-to/feature-sets.md).
