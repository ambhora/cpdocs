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
whole pipeline for one ref is @apidocs::cpdocs.build.build_graph. Adding a build system means
implementing the contract.

## Languages

Each language is a package below `cpdocs.languages` with three parts:

- `extract.py` provides `extract_unit(unit, context)`, which turns a manifest unit of the language
  into an API graph; the build looks it up by the unit's semantic language.
- `entities.py` declares the [entity kinds](../reference/entity-kinds.md) of the language, each
  with its label, badge, order in member lists, member heading and roles. An entity of a kind its
  language does not declare is rejected.
- `render.py` spells declarations and signatures the way the language writes them.

Adding a kind is one entry in `entities.py`; adding a language is a new package registered in
`cpdocs.languages`.

## Renderer resources

The renderer keeps its static content in `share/cpdocs/api/`: page and redirect templates, the
default API introduction, page fragments, the stylesheet and the scripts. They are read through
`importlib.resources`, and the wheel installs `share/` at its root, so they work without a source
checkout. Browser assets are copied into each site's `assets/` directory under content-derived
names, so browsers never keep a stale copy. Test-only sources live in `test/share/`.

## Imports

cpdocs code imports modules, never their members, and names a member where it is used:
`import pathlib` and `pathlib.Path`, `import cpdocs.model` and `cpdocs.model.ApiGraph`. A reader
sees where every name comes from, and no module depends on what another happens to re-export, so
package `__init__` files are empty. `from __future__ import annotations` is the one exception. Ruff
rejects relative imports (TID252), and `test/test_import_style.py` rejects every other `from`
import.
