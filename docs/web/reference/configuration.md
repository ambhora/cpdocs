<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs.yml

`docs/cpdocs.yml` contains only cpdocs orchestration and presentation policy. The build system owns
all project semantics: features, valid feature combinations, generated code, targets, headers and
sources.

The file is read as [Korml](https://ambhora.github.io/korml/), the JSON-shaped subset of YAML:
mappings, sequences, scalars, comments, flow collections and block scalars. Anchors, aliases, tags,
complex keys and duplicate keys are errors. Every scalar is text, so `versions: [1.10]` names the
version `1.10` and does not become the number 1.1; cpdocs decodes the few values it needs as numbers,
such as the bounds of a Keyso `_interval`.

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
| `site.theme.logo` | none | image shown before the project name in the top bar |
| `site.theme.favicon` | `site.theme.logo` | image used as the favicon |
| `site.theme.stylesheet` | none | CSS file loaded after the cpdocs stylesheet |
| `site.theme.colors.light`, `site.theme.colors.dark` | cpdocs colours | colours of each scheme, see [Theme](#theme) |
| `api.hide.cpp-namespaces` | none | glob patterns of C++ namespaces omitted with their contents |
| `api.hide.python-modules` | `private` | `private` hides modules beginning with `_` from the API, while their files stay in the file hierarchy; `none` shows them |
| `checks.undocumented` | `ignore` | `warn` or `fail` when public entities have no documentation |
| `checks.broken-references` | `warn` | `ignore`, `warn` or `fail` for unknown `@apidocs` targets |

The same current `cpdocs.yml` orchestration commands are used for every checkout in `versions`; old tags do not need to carry their own cpdocs configuration.

The first entry in `versions` is the default version of the published API site.
For local ProperDocs serving, the current working tree is temporarily placed first so uncommitted
changes are visible.

## Theme

`site.theme` presents the API site in the project's colours and with its logo, so that the
reference matches the project documentation it links back to. Every key is optional; without
`site.theme` the site keeps the cpdocs look.

```yaml
site:
  theme:
    logo: share/brand/icon.svg
    stylesheet: docs/api.css
    colors:
      light:
        accent: "#266c7c"
        accent-2: "#eba333"
        selected: "#e6f0f2"
      dark:
        accent: "#65a9ba"
        accent-2: "#eba333"
        on-accent: "#0d1f24"
        selected: "#1d3940"
```

Paths are relative to the project root. The logo and the favicon are SVG, PNG, ICO, WebP, JPEG or
GIF images; without a favicon, the logo serves as one. The theme is taken from the current tree for
every entry of `versions`, so older versions are presented the way the project looks today.

The API site has a light and a dark scheme, and the reader switches between them. `colors.light`
and `colors.dark` each set any of the colours below; a colour that a scheme does not set keeps its
cpdocs value in that scheme. Values are hexadecimal, `#rgb`, `#rgba`, `#rrggbb` or `#rrggbbaa`, and
must be quoted, because an unquoted `#` starts a comment.

| Colour | Used for |
| --- | --- |
| `accent` | links, heading rules, the current outline entry and the project documentation button |
| `accent-2` | secondary rules, such as the marks of section headings and the feature-set cards |
| `on-accent` | text on the accent, such as the label of the project documentation button |
| `background` | page background |
| `foreground` | body text |
| `muted` | secondary text |
| `border` | borders and separators |
| `soft` | background of hovered and highlighted areas |
| `selected` | background of selected entries |

`stylesheet` is for anything the colours do not cover. cpdocs writes the colours and then the
stylesheet into `assets/cpdocs-theme.css`, which every page loads after the cpdocs stylesheet. The
class names of the cpdocs pages are not a stable interface; rules on them may need adjusting when
cpdocs changes.
