// --------------------------------------------------------------------------------------------------
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
// --------------------------------------------------------------------------------------------------
#pragma once

#include <cstddef>

/// Scaling of vectors, on the host or on a GPU, optionally distributed with MPI.
namespace demo {

/// Multiply every element of a vector by a factor.
///
/// @param values  the elements, scaled in place
/// @param count   the number of elements
/// @param factor  the factor
void scale(double* values, std::size_t count, double factor);

#if DEMO_HAVE_MPI
/// Multiply every element of a vector distributed over the ranks of an MPI communicator.
///
/// @param values        the local elements, scaled in place
/// @param count         the number of local elements
/// @param factor        the factor
/// @param communicator  the MPI communicator, as a Fortran handle
void scale(double* values, std::size_t count, double factor, int communicator);
#endif

} // namespace demo
