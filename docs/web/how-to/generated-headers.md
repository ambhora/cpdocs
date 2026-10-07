<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Document generated headers

Generated API files must exist before the build command returns. The project provider lists the
generated directory in `manifest.json` with `generated: true`, and the configured build command runs
the target that produces it before cpdocs starts extraction.

For example:

```yaml
build:
  build: >
    cmake -S "{{source}}" -B "{{tmpdir}}" -G Ninja
    -DCPDOCS_FEATURE_SET="{{feature-set}}"
    -DCPDOCS_MANIFEST_OUTPUT="{{output-file}}"
    && cmake --build "{{tmpdir}}" --target generate-api-header
```

The corresponding manifest can expose both checked-in and generated API roots:

```json
{
  "id": "acme",
  "language": "cpp",
  "api": [
    {"path": "/src/include"},
    {"path": "/tmp/build/generated/include", "generated": true}
  ]
}
```

Generated files are rendered like other source files and marked as generated because they have no
location in the repository. The complete example is `examples/generated-cpp`.
