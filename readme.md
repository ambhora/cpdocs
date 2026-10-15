<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, CUDA, HIP, Fortran, Python and Rust projects.

It asks the project's build system, through a small JSON contract, for the concrete feature sets to
document. It builds each feature set independently, consumes the resulting manifest, extracts the API
with Clang for C-family languages, source modules for Fortran, `ast` for Python or rustdoc JSON for
Rust, and merges the results. Implementation files from the manifest are kept in the file hierarchy
without becoming API entities.
Feature-set availability and API language are tracked independently. The versions
to publish are an explicit ordered list in `cpdocs.yml`.

```console
cpdocs build          # document the working tree into build/cpdocs/current
cpdocs versions       # document the configured versions
properdocs build      # project website with the versioned API mounted
```

## Language configurations

The optional `languages` field in `docs/cpdocs.yml` is a [Keyso configuration
space](https://ambhora.github.io/keyso/language/syntax/). cpdocs expands it using pykeyso,
then runs `build.feature-sets` once per concrete configuration and `build.build` once per
feature set discovered for that configuration. Both command templates receive dotted placeholders
from the resulting nested dictionaries, such as `{{cxx.standard}}`, `{{c.standard}}`,
`{{fortran.standard}}`, `{{python.version}}`, or `{{rust.edition}}`. The build system decides
how to apply each value; cpdocs does not translate them into compiler flags.

```yaml
languages:
  _product:
    - cxx:
        _nested:
          standard: [17, 20, 23]
    - python:
        _nested:
          version: ["3.11", "3.12"]

build:
  feature-sets: >-
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DPROJECT_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >-
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DCMAKE_CXX_STANDARD="{{cxx.standard}}"
    -DPROJECT_FEATURE_SET="{{feature-set}}"
    -DPROJECT_CPDOCS_OUTPUT="{{output-file}}"
    && cmake --build "{{tmpdir}}" --target project.cpdocs
```

Use `_set` for explicitly paired combinations rather than the `_product` Cartesian product:

```yaml
languages:
  _set:
    - cxx: {standard: 17}
      python: {version: "3.11"}
    - cxx: {standard: 23}
      python: {version: "3.12"}
```

Each concrete configuration has its own work directory. The merged API records both the
language configuration and feature set in symbol availability, including overload signatures.
If `languages` is omitted, cpdocs performs the original single build configuration, and the
existing `{{source}}`, `{{tmpdir}}`, `{{output-file}}`, `{{feature-set}}`, and `{{python}}`
placeholders continue to work unchanged.

### Language-version availability

cpdocs determines availability from the public declarations extracted for **each concrete
language configuration and discovered feature set**. It does not inspect or require any
cpdocs-specific annotations. C/C++ projects can use their usual `#if __cplusplus` or
`__STDC_VERSION__` guards; Clang analyzes the resulting declarations using the standard and
flags supplied by the project's manifest. Rust and Fortran availability likewise follows the
API that the configured provider extracts.

For Python, the static extractor recognizes native `sys.version_info` comparisons (including
`sys.version_info[:2]`, `.major`/`.minor`, imported aliases, `elif`/`else`, and simple boolean
combinations) for a configured `python.version`. It selects those branches without importing
or executing project code. Guards it cannot evaluate are not interpreted as unconditional
availability; API definitions nested in such guards are omitted as before. Projects with
complex dynamic exports should provide a version-specific manifest/provider rather than
rely on this limited static analysis. Python source parsing uses the host cpdocs interpreter,
so syntax introduced after that interpreter's release may require running cpdocs with a newer
interpreter; this is not equivalent to testing the package on each target interpreter.

The generated API displays language versions/standards separately from feature sets for each
function and overload, with links to the exact combinations of the two. Only configurations
actually analyzed are shown: `C++20` and `C++23` do **not** imply `C++20+`, and API presence
does not assert that functionality was tested.

The configuration lives in `docs/cpdocs.yml`, the API introduction in `docs/api/index.md` and the
ProperDocs pages in `docs/web`. The documentation starts at `docs/web/index.md`; the `examples/`
directory holds standalone projects that the test suite builds.

## Development

```console
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The C and C++ tests need `clang++`, `cmake` and `ninja`. Building the Rust example/site also needs
the nightly toolchain pinned by `examples/rust-basic/rust-toolchain.toml`.
