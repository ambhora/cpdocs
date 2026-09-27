<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document generated headers

Headers produced during the build are listed as `GENERATED` API roots, and the targets that
produce them as `DEPENDS`:

```cmake
cpdocs_api(UNIT acme LANGUAGE cpp TARGET acme_generated
  API include GENERATED ${GENERATED_INCLUDE} DEPENDS generate-api-header)
```

The adapter's `cpdocs-prepare` target builds the `DEPENDS` targets before it writes the variant
manifest, so the headers exist when Clang reads them. Generated files are rendered like any other
source file and marked as generated, since they have no location in the repository.

The complete example is `examples/generated-cpp`.
