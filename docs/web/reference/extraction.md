<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Extraction

## C and C++

Clang parses one generated translation unit that includes every header below the unit's API roots,
with the options from the manifest. cpdocs reads Clang's semantic AST: namespaces, records,
enums, functions and overloads, templates, type aliases, variables and public members. Private and
protected members are left out.

Template parameter lists, requires-clauses and concept definitions are shown as written in the
header. Partial and explicit specializations are separate entities, such as `vec<T, 0>`, listed on
the page of their primary template; deduction guides are listed with the class template they
deduce. When overloads exist in different feature sets, each overload shows its own feature sets.

Macros are not part of the AST. cpdocs lists the `#define`s in API headers that are active in the
feature set, so conditional macros carry feature sets like declarations. Include guards are skipped.

For C, `typedef struct ring {...} ring;` documents the tag once. Enumerators are qualified by their
enumeration, also where the language does not scope them.

## Python

The package is parsed with the standard `ast` module and never imported. Modules, classes,
protocols, functions, methods, properties, upper-case constants, names listed in `__all__`,
annotated attributes and type aliases are documented. `self` and `cls` are not shown. A string
literal directly below an assignment documents it.

## Rust

cpdocs reads the JSON that `rustdoc --output-format json` writes. The build system produces it and
names it in the manifest.


## Fortran

cpdocs reads Fortran module source directly. Public modules, derived types, functions and subroutines
are extracted from `.f`, `.for`, `.ftn`, `.f77`, `.f90`, `.f95`, `.f03`, `.f08`, and `.f18` source
files. A module-level `private` default together with `public :: name` declarations is respected.
Fortran source files from the manifest's `sources` roots remain browseable even when they are not API.
