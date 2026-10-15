<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs example: multiple C++ standards

One CMake project documented under **C++17**, **C++20**, and **C++23** with a single
`cpdocs build` invocation. `docs/cpdocs.yml` declares a Keyso language space and passes
`{{cxx.standard}}` to both CMake commands. CMake uses the same selected standard to build
the library and to populate the manifest's `parse.standard` for Clang.

The source uses the native `__cplusplus` preprocessor macro:

| Declaration | C++17 | C++20 | C++23 |
| --- | :---: | :---: | :---: |
| `demo::always()` | Yes | Yes | Yes |
| `demo::legacy_only()` | Yes | No | No |
| `demo::cxx20_only()` | No | Yes | Yes |
| `demo::cxx23_only()` | No | No | Yes |
| `demo::convert(int)` | Yes | Yes | Yes |
| `demo::convert(double)` | No | Yes | Yes |
| `demo::convert(long double)` | No | No | Yes |

cpdocs merges the three extracted APIs and lists **only observed standards** in each
function's documentation and in each overload's availability information.

Run from this example's directory (requires pykeyso, CMake, Ninja, Clang, and a compiler
with C++23 support):

```console
cpdocs build
properdocs build  # optional full site; requires a Git repository
```

Generated API pages appear under `build/cpdocs/current/`. The build also compiles a real
library for each standard, so a misconfigured or unsupported C++ standard fails rather
than being mistaken for an absent declaration.
