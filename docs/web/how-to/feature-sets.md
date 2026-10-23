<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document build variants

Many projects expose a different API in different builds: an MPI overload only when MPI is enabled,
a GPU implementation only in GPU builds. cpdocs documents every variant and merges them into one
reference in which each declaration and each overload lists the variants it exists in.

The build system knows which variants are valid, so it lists them. cpdocs calls two hooks,
the commands under `build` in `cpdocs.yml`:

1. `build.feature-sets` writes the list of variants to `feature-sets.json`;
2. `build.build` receives one variant in `feature-set.json`, builds it as far as needed and writes
   its `manifest.json`.

cpdocs runs the second hook once per variant. A variant is a plain list of project features; cpdocs
does not interpret the names.

## A variant space in plain CMake

The [cmake-variants example](../examples/index.md) has exactly one implementation, `host` or
`gpu`, and MPI optionally. Its `CMakeLists.txt` declares the two axes and lists their product in
the first hook:

```cmake
set(DEMO_IMPLEMENTATIONS host gpu)
set(DEMO_PARALLEL none mpi)

if(CPDOCS_FEATURE_SETS_OUTPUT)
  set(_variants "")
  foreach(_implementation_value IN LISTS DEMO_IMPLEMENTATIONS)
    foreach(_parallel_value IN LISTS DEMO_PARALLEL)
      if(_parallel_value STREQUAL "none")
        list(APPEND _variants "{\"features\": [\"${_implementation_value}\"]}")
      else()
        list(APPEND _variants "{\"features\": [\"${_implementation_value}\", \"${_parallel_value}\"]}")
      endif()
    endforeach()
  endforeach()
  # ... write the list to ${CPDOCS_FEATURE_SETS_OUTPUT}
endif()
```

The result is four variants: `host`, `host + mpi`, `gpu` and `gpu + mpi`. In the second hook, the
same `CMakeLists.txt` reads the selected features from `CPDOCS_FEATURE_SET`, configures the build
exactly as an ordinary build with `-DDEMO_FEATURES="gpu;mpi"` would, and describes the result. The
GPU implementation adds a unit whose language is `cuda`, so its declarations are marked **CUDA**.

The cpdocs configuration repeats none of this logic:

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

## What the reference shows

- A declaration present in every variant is shown once and lists all of them.
- An overload present in some variants lists only those, for example the MPI overload of
  `demo::scale` in `host + mpi` and `gpu + mpi`.
- A definition in another language, such as the CUDA overload of `demo::scale`, is a separate
  entry marked with its language, with its own variants.
- The feature-sets page lists every variant with the declarations it adds.

Variants and language standards are independent: with both, cpdocs builds every variant for every
standard. See [Document several language standards](language-standards.md).

The build system can be anything that runs the two hooks: a build framework, a script such as the
`tools/minibuild.py` of the `cpp-features` example, or the bundled Python and Rust providers. See
[Use another build system](other-build-systems.md) and, for the files themselves, the
[build-system contract](../reference/contract.md).
