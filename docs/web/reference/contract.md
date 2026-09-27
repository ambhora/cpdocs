<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Build-system contract

cpdocs and a build system exchange three JSON documents: a **request** written by cpdocs, a
**describe manifest** and a **variant manifest** written by the build system. This page is the
normative description of version 1. The reading and checking of the manifests is implemented in
@apidocs::cpdocs.contract.

## Procedure

For every ref it documents, cpdocs

1. writes a describe request and runs `build.describe` from the ref's `cpdocs.yml`;
2. reads the describe manifest and chooses variants by the ref's policy, `all` or `primary`;
3. for each chosen variant, writes a variant request and runs that variant's `commands`;
4. reads the variant manifest, checks it against the describe manifest, and extracts every unit.

Commands are argv lists. They run without a shell, in the source directory, with `CPDOCS_REQUEST`
and `CPDOCS_MANIFEST` in the environment. A non-zero exit status fails the ref. These placeholders
are replaced in every argument:

| Placeholder | Value |
| --- | --- |
| `{source}` | source directory of the ref being documented |
| `{build}` | fresh build directory for this request |
| `{request}` | path of the request file |
| `{manifest}` | path the manifest must be written to |
| `{python}` | the Python interpreter running cpdocs |
| `{cpdocs.cmake}` | the CMake adapter shipped with cpdocs |

## Request

```json
{
  "cpdocs-request": 1,
  "phase": "variant",
  "ref": "v1.2.0",
  "ref-kind": "tag",
  "variant": "full",
  "source": "/ci/checkout",
  "build": "/ci/checkout/build/cpdocs/work/v1.2.0/variants/full/build",
  "manifest": "/ci/checkout/build/cpdocs/work/v1.2.0/variants/full/manifest.json"
}
```

`phase` is `describe` or `variant`; `variant` is `null` for describe requests. `ref-kind` is
`branch`, `tag` or `worktree`.

## Describe manifest

```json
{
  "cpdocs-manifest": 1,
  "kind": "describe",
  "generator": "cpdocs.cmake / CMake 3.28.3",
  "project": {"name": "demo-solver", "version": "1.2.0"},
  "features": {"PROJECT_FEATURES": {"values": ["mpi", "cuda"]}},
  "units": [{"id": "demo", "language": "cpp"}],
  "variants": [
    {"name": "serial", "primary": true, "features": {"PROJECT_FEATURES": []},
     "commands": [["cmake", "-S", "{source}", "-B", "{build}", "..."]]}
  ]
}
```

- `features` declares the feature axes and their valid values. It may be empty.
- `units` lists the documentation units. `language` is `c`, `cpp`, `python` or `rust`; `id` must
  be unique and stable across variants.
- `variants` must be non-empty, with unique names and exactly one `primary` variant. Each variant
  assigns every axis a subset of its values; an omitted axis selects no value.

## Variant manifest

```json
{
  "cpdocs-manifest": 1,
  "kind": "variant",
  "variant": "full",
  "features": {"PROJECT_FEATURES": ["mpi", "cuda"]},
  "units": [
    {"id": "demo", "language": "cpp",
     "api": [{"path": "include"}, {"path": "/build/generated", "generated": true}],
     "parse": {"standard": "c++20", "include": ["include"], "system-include": [],
               "define": ["DEMO_HAVE_MPI=1"], "flags": [], "compile-database": null}}
  ]
}
```

`variant` and `features` repeat what the build system was configured with. cpdocs rejects the
manifest when they differ from the request and the describe manifest, or when its units differ
from the described units.

Relative paths are relative to the source directory. The fields of a unit depend on its language:

| Language | Fields |
| --- | --- |
| `c`, `cpp` | `api`: one or more directories whose headers form the API; `parse`: options for Clang |
| `python` | `api`: exactly one package directory; `package`: the import name |
| `rust` | `rustdoc-json`: the JSON written by `rustdoc --output-format json` |

Every field of `parse` is optional. `compile-database` names a `compile_commands.json` from which
the options of one representative translation unit are taken; the explicit fields are added after
them.
