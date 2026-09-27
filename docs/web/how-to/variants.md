<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document feature variants

A project whose API depends on build features declares the features and the variants to document
in its build system. cpdocs builds every declared variant and records, per entity, the variants in
which it exists. This guide uses CMake and the besa feature convention.

## Declare the feature axis

```cmake
include(cmake/feature.cmake)
set(PROJECT_FEATURES "none" CACHE STRING "Optional features: none, mpi, cuda, or all")
besa_feature(PROJECT_FEATURES VALUES "mpi;cuda" DESCRIPTION "Optional solver features")

if(PROJECT_FEATURES_MPI)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_MPI=1)
endif()
```

The mapping from a feature to a compile definition stays in the build system; cpdocs never sees it.

## Declare the variants

```cmake
if(COMMAND cpdocs_api)
  cpdocs_features(PROJECT_FEATURES)
  cpdocs_variant(serial PRIMARY PROJECT_FEATURES none)
  cpdocs_variant(mpi PROJECT_FEATURES mpi)
  cpdocs_variant(full PROJECT_FEATURES all)
  cpdocs_api(UNIT demo LANGUAGE cpp TARGET demo API include)
endif()
```

`cpdocs_features` takes the valid values from `PROJECT_FEATURES_ARRAY`, which `besa_feature`
sets. The primary variant is the one built when only one variant is wanted.

## Build fewer variants for branches

Which refs build all variants is publishing policy, set in `docs/cpdocs.yml`:

```yaml
versions:
  branches:
    include: [main]
    variants: primary
  tags:
    variants: all
```

The complete example is `examples/cpp-features`.
