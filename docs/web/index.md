<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, Python and Rust projects. It
reads declarations the way the compiler or interpreter sees them, merges every documented variant
of the API into one reference, and publishes one directory per Git branch or tag.

cpdocs does not know how a project is built. It asks the project's build system, through a small
[contract](reference/contract.md), which variants exist and how to read each of them. CMake support
ships with cpdocs; any other build system implements the same two JSON manifests.

```console
cpdocs build          # document the working tree
cpdocs versions       # document the configured branches and tags
properdocs build      # build the project website with the API mounted
```

Start with the [tutorial](tutorials/first-reference.md).
