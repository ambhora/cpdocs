# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(meta VERSION 0.4.0 LANGUAGES CXX)

add_library(meta INTERFACE)
target_compile_features(meta INTERFACE cxx_std_20)
target_include_directories(meta INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

if(COMMAND cpdocs_api)
  cpdocs_api(UNIT meta LANGUAGE cpp TARGET meta API include)
endif()
