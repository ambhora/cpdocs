// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0

use crate::geometry::Vector3;

// Implementation-only helper. It is browseable in the file hierarchy but is not public API.
pub(crate) fn norm_squared(value: Vector3) -> f64 {
    value.x * value.x + value.y * value.y + value.z * value.z
}
