<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Command line

```text
cpdocs build [--config docs/cpdocs.yml] [--output build] [--tmp-directory DIR] [--label main]
cpdocs versions [--config docs/cpdocs.yml] [--output build] [--tmp-directory DIR]
cpdocs manifest python feature-sets ...
cpdocs manifest python build ...
cpdocs rust feature-sets --source <project> --output <feature-sets.json>
cpdocs rust build --source <project> --feature-set <feature-set.json> --output <manifest.json>
```

`build` documents the working tree into `<output>/cpdocs/current`. It always documents every
feature set returned by `build.feature-sets`.

`versions` documents the exact ordered `versions:` list from `cpdocs.yml` into
`<output>/cpdocs/versions`.

`manifest python` is a small provider for plain Python projects.

`rust` is the built-in Cargo provider. `rust feature-sets` reads Cargo metadata. By default every
declared Cargo feature is treated as a disjoint feature set and documented once; projects that need
specific combinations can list them in `[package.metadata.cpdocs]`. `rust build` runs Cargo rustdoc
with nightly JSON output and writes a normal cpdocs manifest.

By default, feature-set inputs, manifests, scratch/build directories and command logs are kept below
`<output>/cpdocs/work/<version>/feature-sets/`. Pass `--tmp-directory DIR` to keep this workspace
under `DIR/cpdocs/work/` while leaving rendered output under `<output>/cpdocs/`.
