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

The configuration lives in `docs/cpdocs.yml`, the API introduction in `docs/api/index.md` and the
ProperDocs pages in `docs/web`. The documentation starts at `docs/web/index.md`; the `examples/`
directory holds standalone projects that the test suite builds.

## Development

```console
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The C and C++ tests need `clang++`, `cmake` and `ninja`; they are skipped when these are missing.
