// SPDX-FileCopyrightText: 2026 cpdocs developers
// SPDX-License-Identifier: Apache-2.0
#pragma once

/// Geometry primitives.
namespace geom {

/// A three-dimensional vector.
struct vector3 {
    /// Components.
    double x{}, y{}, z{};
};

/// Dot product of two vectors.
double dot(vector3 const& a, vector3 const& b) noexcept;

#if GEOM_HAVE_SIMD
/// Dot products of many vector pairs at once.
void dot_many(vector3 const* a, vector3 const* b, double* out, int count) noexcept;
#endif

} // namespace geom
