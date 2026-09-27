# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(cpdocs-basic-example VERSION 1.0.0 LANGUAGES CXX)

add_library(acme_math STATIC src/math.cpp)
target_compile_features(acme_math PUBLIC cxx_std_20)
target_include_directories(acme_math PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(COMMAND cpdocs_api)
  cpdocs_api(UNIT acme_math LANGUAGE cpp TARGET acme_math API include)
endif()
