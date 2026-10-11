// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#include "geom/vector.hpp"

double geom::dot(vector3 const& a, vector3 const& b) noexcept {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}
