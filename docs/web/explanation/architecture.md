<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Architecture

cpdocs is a pipeline with a single boundary to the outside:

1. **Contract.** The build system describes the project and configures each variant. cpdocs only
   reads the manifests.
2. **Extraction.** Each unit of each variant becomes an API graph: Clang for C and C++, `ast` for
   Python, rustdoc JSON for Rust.
3. **Merge.** The graphs of all units of a variant are combined; the variant graphs are then merged
   so that every entity records the variants it exists in.
4. **Rendering.** The merged graph becomes a standalone HTML site. Versions are rendered
   independently and joined by `versions.json`.

The API graph, @apidocs::cpdocs.model.ApiGraph, is the only interface between the stages; the
whole pipeline for one ref is @apidocs::cpdocs.build.build_graph. Adding a language means adding an
extractor that produces it; adding a build system means implementing the contract.
