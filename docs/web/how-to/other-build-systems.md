<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Use a build system other than CMake

cpdocs talks to a build system only through the [contract](../reference/contract.md). A build
system supports cpdocs by answering two requests:

1. **describe**: write the project name, feature axes, units and variants, with the commands that
   configure each variant;
2. **variant**: write, per unit, the API roots and the options needed to parse them.

`examples/cpp-features/tools/minibuild.py` is a complete implementation in about seventy lines of
Python. Its configuration names it as the describe command:

```yaml
contract: 1
build:
  describe:
    - ["{python}", tools/minibuild.py, "{request}"]
```

The test suite checks that it produces the same API reference as the CMake build of the same
project.

## Plain Python packages

A package built with a standard backend such as hatchling needs no configuration step. cpdocs' own
helper answers the requests for it:

```yaml
contract: 1
build:
  describe:
    - ["{python}", -m, cpdocs, manifest, python, --request, "{request}",
       --package, dice, --source, src/dice]
```

It reads the project name and version from `pyproject.toml` and documents one `default` variant.
