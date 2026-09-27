<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# CMake adapter

`cpdocs.cmake` implements the [contract](contract.md) for CMake 3.24 and newer. cpdocs injects it
with `-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES={cpdocs.cmake}` and passes the request with
`-DCPDOCS_REQUEST={request}`. Projects call its functions behind `if(COMMAND cpdocs_api)`.

## Functions

```cmake
cpdocs_features(<axis> [VALUES <value>...])
```

Declares a feature axis. Without `VALUES`, the values are read from `<axis>_ARRAY`, as set by
`besa_feature`. The axis variable holds the selected values; `none` and `all` select no value or
every value.

```cmake
cpdocs_variant(<name> [PRIMARY] [<axis> <value>...]...)
```

Declares a variant. An axis it does not mention keeps the value of the describe configuration.
Without any `cpdocs_variant`, the project has one primary variant `default`; without `PRIMARY`,
the first variant is primary.

```cmake
cpdocs_api(UNIT <id> LANGUAGE <c|cpp|python|rust>
           [TARGET <target>] [API <dir>...] [GENERATED <dir>...]
           [STANDARD <std>] [DEFINE <definition>...] [INCLUDE <dir>...]
           [PACKAGE <python package>] [RUSTDOC_JSON <file>] [DEPENDS <target>...])
```

Declares a documentation unit. For C and C++, include directories, system include directories,
compile definitions and compile options come from the interface usage requirements of `TARGET`, so
header-only `INTERFACE` libraries need no compiled source. The standard is the highest `cxx_std_*`
or `c_std_*` compile feature of the target unless `STANDARD` is given. `API` and `INCLUDE` are
relative to the current source directory, `GENERATED` and `RUSTDOC_JSON` to the current binary
directory.

## Answering requests

At the end of the top-level `CMakeLists.txt`, the adapter answers the request. A describe request
is answered directly. Each variant's commands configure the project with the variant's axis values
and build `cpdocs-prepare`, which builds the `DEPENDS` targets and writes the variant manifest.
`CMAKE_BUILD_TYPE`, `CMAKE_TOOLCHAIN_FILE` and the list `CPDOCS_CONFIGURE_ARGS` of the describe
configuration are passed on to every variant.

Definitions and options containing `;` are not supported.
