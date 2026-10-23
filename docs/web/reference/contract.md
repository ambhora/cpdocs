<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Build-system contract

cpdocs has no configure or build model of its own. It talks to the project's build system through
two hooks, the commands `build.feature-sets` and `build.build` in `cpdocs.yml`, and two JSON files
each of them writes. For each version and language configuration it runs this loop:

1. run `build.feature-sets` once;
2. read `feature-sets.json`;
3. for every listed feature set, write one `feature-set.json`;
4. run `build.build` once for that file;
5. read the resulting `manifest.json` and extract the API;
6. merge the APIs from all feature sets.

The build command therefore always handles **one concrete feature set**, never a list of feature
sets.

## Hooks

Both hooks in `cpdocs.yml` are shell command strings run from the source directory.

`build.feature-sets` may use:

| Placeholder | Value |
| --- | --- |
| `{{source}}` | source directory being documented |
| `{{tmpdir}}` | fresh scratch directory for discovery |
| `{{output-file}}` | path where `feature-sets.json` must be written |
| `{{python}}` | Python running cpdocs, for helper providers |

`build.build` may use:

| Placeholder | Value |
| --- | --- |
| `{{source}}` | source directory being documented |
| `{{tmpdir}}` | fresh build directory for this one feature set |
| `{{feature-set}}` | selected `feature-set.json` |
| `{{output-file}}` | path where this build must write `manifest.json` |
| `{{python}}` | Python running cpdocs |

A non-zero command status fails the documentation build.

cpdocs never pastes a placeholder's value into the command text. Each placeholder becomes a
reference to an environment variable holding its value, `CPDOCS_ARG_` followed by the name in upper
case with `.` and `-` turned into `_`: `{{output-file}}` becomes `${CPDOCS_ARG_OUTPUT_FILE}` and a
language property `{{cxx.standard}}` becomes `${CPDOCS_ARG_CXX_STANDARD}`. The shell expands the
reference after it has parsed the command, so a value is never run as shell syntax, whatever it
contains. Quote placeholders as in the examples, `"{{source}}"`, so that a value with spaces stays one
argument; a build script may also read the variables directly. Two placeholders that map to the same
variable, such as `output-file` and a language property `output_file`, are rejected.

## `feature-sets.json`

Feature sets are deliberately **unnamed**. A feature set is just one concrete list of project
features:

```json
{
  "cpdocs-feature-sets": 1,
  "generator": "CMake 4.3.4",
  "project": {"name": "demo", "version": "2.0.0"},
  "feature-sets": [
    {"features": ["host"]},
    {"features": ["gpu"]},
    {"features": ["gpu", "mpi"]}
  ]
}
```

cpdocs requires a project name, a non-empty `feature-sets` list, and a `features` list on every
entry. Feature names are project-defined strings. Additional fields are owned by the build system;
cpdocs preserves them when it writes the selected feature set back.

For the final entry above the build command receives:

```json
{
  "cpdocs-feature-set": 1,
  "features": ["gpu", "mpi"]
}
```

The list of features is used only for availability in the generated reference. It does **not** tell
cpdocs which programming language an API definition uses.

## `manifest.json`

The manifest describes only the artifacts resulting from one selected build. It does **not** repeat
the selected feature set. Each unit has a semantic `language`, which is independent of its feature
set:

```json
{
  "cpdocs-manifest": 1,
  "units": [
    {
      "id": "device",
      "language": "cuda",
      "api": [
        {"path": "/src/include"},
        {"path": "/tmp/build/generated/include", "generated": true}
      ],
      "parse": {
        "language": "cpp",
        "compile-database": "/tmp/build/compile_commands.json"
      }
    }
  ]
}
```

Here `language: cuda` is API metadata and is rendered as the **CUDA** badge. `parse.language: cpp`
only selects the extraction frontend. This distinction allows a project feature such as `gpu` to
enable a CUDA API without conflating the feature name with the language.

Relative paths are relative to the source directory. Fields depend on language:

| Semantic language | Fields |
| --- | --- |
| `c`, `cpp`, `cuda`, `hip` | `api`: public header roots; `parse`: Clang environment |
| `python` | `api`: exactly one package directory; `package`: import name |
| `rust` | `rustdoc-json`: JSON produced by rustdoc; `sources` may expose the crate tree for browsing |
| `fortran` | `modules`: Fortran module source roots; optional `api` roots |

`parse.language` is currently `c` or `cpp`. CUDA and HIP units normally use `cpp` while keeping
their semantic language unchanged.

The optional `headers`, `sources`, `modules`, and `executables` fields describe the project files
produced or consumed by the unit. cpdocs uses them for the file hierarchy only; they do not expand
the API boundary. This is why implementation files can be browsed without becoming API entities.
For Fortran, `modules` is also the natural public declaration source and is parsed as API.

Every file read from these roots is published, so cpdocs reads a file only if, after following
symbolic links, it lies below the declared root or the project; a link from a source tree to
anything else is skipped. Inside a Git checkout, a unit that is not marked `generated` publishes
only files Git tracks, so untracked local files such as credentials never reach the site. The same
link rule applies to API roots, Python packages and Rust sources; rustdoc spans into dependencies
outside the project keep their location but their source is not published.

For C-family APIs a compile database is preferred when available. Explicit API roots still matter:
a compilation database describes how translation units are compiled, not which headers are public.
