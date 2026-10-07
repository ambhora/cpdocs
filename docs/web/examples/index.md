<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Examples

Every directory in `examples/` is a standalone project with its own `docs/cpdocs.yml` and
ProperDocs site. The test suite builds them, and the root ProperDocs site mounts each example directly during its
own build. Each example site is versioned with its explicit `versions:` list.

| Example | Shows | Site |
| --- | --- | --- |
| `basic-cpp` | one compiled C++ library | [basic-cpp](basic-cpp/) |
| `cpp-templates` | specializations, concepts, requires-clauses, SFINAE and deduction guides | [cpp-templates](cpp-templates/) |
| `cpp-features` | feature-dependent API across three feature sets; the same project through `tools/minibuild.py` | [cpp-features](cpp-features/) |
| `generated-cpp` | headers generated during the build | [generated-cpp](generated-cpp/) |
| `c-basic` | a C library | [c-basic](c-basic/) |
| `mixed` | a C++ unit and a Python unit in one project | [mixed](mixed/) |
| `fortran-basic` | a Fortran module plus an implementation-only source file | [fortran-basic](fortran-basic/) |
| `python-basic` | a plain Python package, answered by `cpdocs manifest python` | [python-basic](python-basic/) |
| `rust-basic` | Cargo features plus nightly rustdoc JSON, with private implementation source still browseable | [rust-basic](rust-basic/) |

There is no separate example-site build step. Both `properdocs build` and `properdocs serve` build
these sites directly at `examples/<name>/`; during `serve`, they use the checked-out working tree.
