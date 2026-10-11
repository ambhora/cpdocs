# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
"""Fortran extraction and rendering."""

from .extract import extract_fortran_graph
from .render import RENDERING

__all__ = ["RENDERING", "extract_fortran_graph"]
