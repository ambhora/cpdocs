<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# cpdocs generated-header example

Part of the public API of this library exists only in the build directory: no generated header is
checked in. cpdocs documents it because its build hook runs the generators before cpdocs reads the
headers.

- @apidocs::acme::version comes from `acme/version.hpp`, written by `configure_file` from a template
  when the build is configured.
- @apidocs::acme::status comes from `acme/status.hpp`, written by a build target from the table
  `data/status-codes.txt`; each row becomes a documented enumerator.
- @apidocs::acme::add is declared in the checked-in header `acme/core.hpp`, which includes both.

The [API reference](api.md) lists every published version.
