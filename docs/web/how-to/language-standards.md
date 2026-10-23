<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document several language standards

A C++ library may offer more API with C++20 than with C++17, and a Python package may guard
definitions with `sys.version_info`. cpdocs documents each language standard or version you list and
marks every declaration and overload with the standards it exists in.

## Listing the standards

`languages` in `cpdocs.yml` is a [Keyso configuration space](https://ambhora.github.io/keyso/language/syntax/).
cpdocs expands it into concrete language configurations, runs `build.feature-sets` once for each,
and builds every variant of each:

```yaml
languages:
  cxx:
    _nested:
      standard: [17, 20, 23]

build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DCPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DCPDOCS_FEATURE_SET="{{feature-set}}"
    -DCPDOCS_MANIFEST_OUTPUT="{{output-file}}"
```

Each value reaches the hooks as a dotted placeholder, such as `{{cxx.standard}}`, `{{c.standard}}`,
`{{fortran.standard}}`, `{{python.version}}` or `{{rust.edition}}`. The build system decides how
to apply it; cpdocs does not turn values into compiler flags.

`_product` combines several languages in every combination, and `_set` lists explicit pairs:

```yaml
languages:
  _set:
    - cxx: {standard: 17}
      python: {version: "3.11"}
    - cxx: {standard: 23}
      python: {version: "3.12"}
```

## How availability is found

Availability comes from the API extracted for each language configuration and variant; no
cpdocs-specific annotations are needed.

- **C and C++** projects use their usual `#if __cplusplus` or `__STDC_VERSION__` guards. Clang
  parses the headers with the standard and flags the manifest gives.
- **Python** guards written with `sys.version_info`, including `sys.version_info[:2]`,
  `.major` and `.minor`, imported aliases, `elif` and `else` and simple boolean combinations, are
  evaluated for the configured `python.version` without importing the package. Definitions under a
  guard cpdocs cannot evaluate are left out. The source is parsed with the Python running cpdocs, so
  syntax newer than that interpreter needs a newer one.
- **Fortran and Rust** follow the API their extractor finds for each configuration.

The reference lists the standards of each declaration and overload separately from its variants.
Only configurations that were analysed are shown: documenting C++20 and C++23 does not claim C++26,
and presence in the API does not claim that a feature was tested.

The [cpp-standards example](../examples/index.md) builds C++17, C++20 and C++23 from one
configuration, with functions added and removed between standards and standard-dependent overloads.
