<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs

cpdocs generates semantic, versioned API documentation for C, C++, CUDA, HIP, Fortran, Python and
Rust projects.

- **Semantic.** cpdocs reads the source with each language's own tools, Clang for the C family,
  Python's `ast`, rustdoc for Rust and a module reader for Fortran, and works from the resulting
  comment-preserving syntax tree. The reference shows declarations as the compiler sees them and is
  rendered as HTML. [Extraction](reference/extraction.md) lists what each language contributes.
- **Versions.** It documents the branches and tags you list, each as its own version of the
  reference. See [Document several versions](how-to/versions.md).
- **Build variants.** Two hooks connect cpdocs to the project's build system: the first lists every
  variant worth documenting, and the second builds one variant and describes its API. See
  [Document build variants](how-to/feature-sets.md).
- **One merged reference.** The APIs of all variants are merged, and every declaration and overload
  shows the variants it is available in. Definitions in different languages, such as a C++ and a
  CUDA implementation, stay separate entries.
- **Language standards.** The same project can be documented for several language standards or
  versions, such as C++17, C++20 and C++23. See
  [Document several language standards](how-to/language-standards.md).
- **ProperDocs.** The reference is a standalone HTML site, and cpdocs integrates with
  [ProperDocs](https://properdocs.org) for the project website around it.
- **Versioned API in an unversioned website.** The cpdocs ProperDocs plugin embeds every version of
  the API below one mount point of the project website, which itself needs no versioning. See
  [Embed the API in a project website](how-to/properdocs.md).

cpdocs keeps no knowledge of the project's features or build: everything it knows about a variant
comes from the build system through the hooks, as described in the
[build-system contract](reference/contract.md).

```console
cpdocs build          # document the working tree
cpdocs versions       # document every listed version
properdocs build      # build the project website with the versioned API mounted
```

Start with the [tutorial](tutorials/first-reference.md).
