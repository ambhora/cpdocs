<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document feature-dependent APIs

The build system owns the finite feature space worth documenting. cpdocs asks for the concrete
feature sets, builds each one independently, and records where each extracted definition exists.

Features and API languages are different concepts. With BESA, for example, a project can define a
host/GPU implementation choice and optional MPI independently:

```cmake
foreach(_feature IN ITEMS host gpu mpi)
  besa_add_feature("${_feature}")
endforeach()

besa_add_variant(implementation ONE_OF host gpu)
besa_add_variant(parallel ZERO_OR_ONE mpi)
besa_keyso_create_feature_set(supported PRODUCT implementation parallel)
besa_set_feature_set(supported)
```

The resulting feature sets can be `host`, `host + mpi`, `gpu`, and `gpu + mpi`. The units selected
by those sets carry their own semantic language (`cpp`, `cuda`, and so on) in the manifest.

The cpdocs configuration repeats none of this project logic:

```yaml
contract: 3
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

If the same qualified function has a C++ definition and a CUDA definition, cpdocs renders two API
entries and marks them **C++** and **CUDA**. If the CUDA definition is identical in both `gpu` and
`gpu + mpi`, it is rendered once and both feature sets are listed in its availability section.
