<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Why the build system owns variants

An API that depends on build features exists in several forms. The reliable way to see each form
is to configure the project the way a user would and read what the compiler then sees.

Only the build system knows how a feature becomes a definition, an include directory or a generated
header, and that knowledge changes from release to release. cpdocs therefore asks each ref's own
build system for its variants and their commands instead of keeping a copy of that knowledge in its
configuration. An old tag is documented with the features it had, and a change of build system
does not change `cpdocs.yml`.

What remains in `cpdocs.yml` is publishing policy: which refs to build, how many variants each
gets, and what the site looks like.
