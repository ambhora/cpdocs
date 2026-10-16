# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
from typing import Protocol, overload


class Reader(Protocol):
    def read(self, path: str, /, *, binary: bool = False) -> bytes: ...


class Solver:
    def __init__(self, value: int):
        self.value = value

    @overload
    def solve(self, value: int) -> int: ...

    @overload
    def solve(self, value: float) -> float: ...
