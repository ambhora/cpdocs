<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Architecture

cpdocs is a pipeline with a single boundary to the outside:

1. **Contract.** The build system enumerates concrete feature sets and builds one selected feature set at a time.
   cpdocs only reads the resulting JSON files.
2. **Extraction.** Each unit of each feature set becomes an API graph. The manifest's semantic
   language (`c`, `cpp`, `cuda`, `hip`, ...) is kept separate from the parser frontend used to
   extract it. Clang handles the current C-family frontends, `ast` handles Python, and rustdoc JSON
   handles Rust.
3. **Merge.** The graphs of all units of a feature set are combined; feature-set graphs are then
   merged. Identical definitions accumulate feature-set availability, while definitions in different
   semantic languages remain distinct API entries.
4. **Rendering.** The merged graph becomes a standalone HTML site. Versions are rendered
   independently and joined by `versions.json`.

The API graph, @apidocs::cpdocs.model.ApiGraph, is the only interface between the stages; the
whole pipeline for one ref is @apidocs::cpdocs.build.build_graph. Adding a language means adding an
extractor that produces it; adding a build system means implementing the contract.
