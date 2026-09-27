<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Python API

cpdocs documents its own Python package with cpdocs. The reference is published for every version;
links without a version, such as @apidocs::cpdocs.build.build_versions, go to the default version.

The modules a build system integration or an extension touches first:

- @apidocs::cpdocs.contract — requests and manifests of the build-system contract
- @apidocs::cpdocs.config.load_config — reading `cpdocs.yml`
- @apidocs::cpdocs.build.build_graph — describe, resolve, extract and merge one ref
- @apidocs::cpdocs.model.ApiGraph — the graph every extractor produces

## Versions

@apidocs-versions
