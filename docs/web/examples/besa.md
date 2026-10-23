<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Example: a build framework that provides the hooks

The cpdocs hooks are ordinary commands, so a build framework can implement them once for every
project that uses it. BESA, a CMake framework, is one such framework. A project declares its
features and how they combine:

```cmake
foreach(_feature IN ITEMS host gpu mpi)
  besa_add_feature("${_feature}")
endforeach()

besa_add_variant(implementation ONE_OF host gpu)
besa_add_variant(parallel ZERO_OR_ONE mpi)
besa_keyso_create_feature_set(supported PRODUCT implementation parallel)
besa_set_feature_set(supported)
```

This is the same variant space as the plain CMake [cmake-variants](../cmake-variants/) example: `host`,
`host + mpi`, `gpu` and `gpu + mpi`. BESA writes both cpdocs files itself, so the project contains no
cpdocs-specific code and `cpdocs.yml` only names BESA's entry points:

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

cpdocs does not depend on BESA, and nothing else in this documentation assumes it. This example is
not built by the test suite, since BESA is not a dependency of cpdocs.
