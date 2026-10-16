# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
import sys as runtime
from sys import version_info as vi


class Service:
    if runtime.version_info >= (3, 12):

        def run(self, value: str) -> str:
            """Run using the modern interface."""
            return value
    else:

        def run(self, value: int) -> int:
            """Run using the legacy interface."""
            return value


if runtime.version_info >= (3, 12):

    def new_api(value: str) -> int:
        """New interface."""
        return 1
elif vi[:2] == (3, 11):

    def old_api(value: int) -> int:
        """Old interface."""
        return 1


if runtime.version_info < (3, 12) or vi.major == 3 and vi.minor == 11:
    LEGACY = 42
