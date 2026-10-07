// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0

/// A three-dimensional vector.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Vector3 {
    /// X component.
    pub x: f64,
    /// Y component.
    pub y: f64,
    /// Z component.
    pub z: f64,
}

/// Return the dot product of two vectors.
pub fn dot(lhs: Vector3, rhs: Vector3) -> f64 {
    lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z
}

/// Return the dot products of corresponding vector pairs.
///
/// This API exists only in the `batch` Cargo feature.
#[cfg(feature = "batch")]
pub fn dot_many(lhs: &[Vector3], rhs: &[Vector3]) -> Vec<f64> {
    lhs.iter()
        .zip(rhs)
        .map(|(&left, &right)| dot(left, right))
        .collect()
}

/// Return a dot product only when both vectors have non-zero length.
///
/// This API exists only in the `checked` Cargo feature.
#[cfg(feature = "checked")]
pub fn checked_dot(lhs: Vector3, rhs: Vector3) -> Option<f64> {
    if crate::internal::norm_squared(lhs) == 0.0 || crate::internal::norm_squared(rhs) == 0.0 {
        None
    } else {
        Some(dot(lhs, rhs))
    }
}
