# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(ring VERSION 0.1.0 LANGUAGES C)

add_library(ring STATIC src/ring.c)
target_compile_features(ring PUBLIC c_std_11)
target_include_directories(ring PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(COMMAND cpdocs_api)
  cpdocs_api(UNIT ring LANGUAGE c TARGET ring API include)
endif()
