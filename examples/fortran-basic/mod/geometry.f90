! SPDX-FileCopyrightText: 2026 cpdocs developers
! SPDX-License-Identifier: Apache-2.0

!> Geometry primitives.
module geometry
  implicit none
  private
  public :: vector3, dot

  !> A three-dimensional vector.
  type :: vector3
    real :: x
    real :: y
    real :: z
  end type vector3

contains

  !> Return the dot product of two vectors.
  real function dot(lhs, rhs) result(value)
    type(vector3), intent(in) :: lhs, rhs
    value = lhs%x * rhs%x + lhs%y * rhs%y + lhs%z * rhs%z
  end function dot

end module geometry
