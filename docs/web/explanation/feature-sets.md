<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->
# Why the build system owns feature sets

Only the build system knows which feature combinations are valid, which generators must run, and
which headers are public in a concrete configuration. Repeating that knowledge in cpdocs would
create a second configuration language that inevitably drifts from the project.

cpdocs therefore consumes an enumerable list of **unnamed feature sets** and passes one selection
back to the build system at a time. It uses the feature list only to record availability.

Programming language is a separate property of the manifest unit. A `gpu` feature can expose a
`CUDA` unit; several different feature sets can expose the same CUDA definition; and a C++
definition can be available in every feature set. During merging, identical definitions accumulate
feature-set availability, while definitions with different semantic languages remain distinct.

Version policy is equally explicit: `versions:` is simply the ordered list of Git branches/tags to
publish. There is no second selector language for branches, tags, ranges, aliases, or feature-set
policies.
