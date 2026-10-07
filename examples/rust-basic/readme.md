<!--
SPDX-FileCopyrightText: 2026 cpdocs developers
SPDX-License-Identifier: Apache-2.0
-->

# cpdocs example: Rust

The public API is extracted from nightly rustdoc JSON. Cargo features are treated as disjoint
feature sets by default: this example documents `batch` and `checked` separately. `src/internal.rs`
is still browseable in the file hierarchy without entering the public API hierarchy.
