<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs.yml

`docs/cpdocs.yml` contains only cpdocs orchestration and presentation policy. The build system owns
all project semantics: features, valid feature combinations, generated code, targets, headers and
sources.

A minimal configuration is:

```yaml
contract: 3

build:
  feature-sets: >
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DBESA_CPDOCS_FEATURE_SETS_OUTPUT="{{output-file}}"
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}"
    -DBESA_CPDOCS_FEATURE_SET="{{feature-set}}"
    -DBESA_CPDOCS_MANIFEST_OUTPUT="{{output-file}}"
    && cmake --build "{{tmpdir}}" --target besa.cpdocs

versions: [main, v2.0.0, v1.0.0]
```

The two commands are the whole build-system interface. `build.feature-sets` runs once per source
version. `build.build` runs once for every feature set returned by the first command.

| Key | Default | Meaning |
| --- | --- | --- |
| `build.feature-sets` | required | command that writes `feature-sets.json` |
| `build.build` | required | command that consumes one `feature-set.json` and writes one `manifest.json` |
| `versions` | `[main]` | exact branch/tag names to document, in publication/default order |
| `site.index` | `docs/api/index.md` | introduction of the API reference |
| `site.copyright` | project developers | footer text |
| `site.project-docs` | `auto` | URL of the project website |
| `api.hide.cpp-namespaces` | none | glob patterns of C++ namespaces omitted with their contents |
| `api.hide.python-modules` | `private` | `private` hides modules beginning with `_`; `none` shows them |
| `checks.undocumented` | `ignore` | `warn` or `fail` when public entities have no documentation |
| `checks.broken-references` | `warn` | `ignore`, `warn` or `fail` for unknown `@apidocs` targets |

The same current `cpdocs.yml` orchestration commands are used for every checkout in `versions`; old tags do not need to carry their own cpdocs configuration.

The first entry in `versions` is the default version of the published API site.
For local ProperDocs serving, the current working tree is temporarily placed first so uncommitted
changes are visible.
