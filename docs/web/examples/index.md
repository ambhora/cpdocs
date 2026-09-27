<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Examples

Every directory in `examples/` is a standalone project with its own `docs/cpdocs.yml` and
ProperDocs site. The test suite builds them, and the published documentation includes each
example's site, versioned with the branches and tags of the cpdocs repository.

| Example | Shows | Site |
| --- | --- | --- |
| `basic-cpp` | one compiled C++ library | [basic-cpp](basic-cpp/) |
| `cpp-templates` | specializations, concepts, requires-clauses, SFINAE and deduction guides | [cpp-templates](cpp-templates/) |
| `cpp-features` | besa-style features and three variants; the same project through `tools/minibuild.py` | [cpp-features](cpp-features/) |
| `generated-cpp` | headers generated during the build | [generated-cpp](generated-cpp/) |
| `c-basic` | a C library | [c-basic](c-basic/) |
| `mixed` | a C++ unit and a Python unit in one project | [mixed](mixed/) |
| `python-basic` | a plain Python package, answered by `cpdocs manifest python` | [python-basic](python-basic/) |

To build the example sites locally after `properdocs build`:

```console
uv run python tools/build_example_sites.py
```
