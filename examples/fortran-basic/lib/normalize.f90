! SPDX-FileCopyrightText: 2026 cpdocs developers
! SPDX-License-Identifier: Apache-2.0

! Implementation-only helper. It is browseable in the file hierarchy but is not part of the API.
subroutine normalize_impl(x, y, z)
  real, intent(inout) :: x, y, z
  real :: length
  length = sqrt(x*x + y*y + z*z)
  if (length > 0.0) then
    x = x / length
    y = y / length
    z = z / length
  end if
end subroutine normalize_impl
