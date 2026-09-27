# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(demo-solver VERSION 1.2.0 LANGUAGES CXX)

# --------------------------------------------------------------------------------------------------
# Features, declared the besa way
# --------------------------------------------------------------------------------------------------
include(cmake/feature.cmake)
set(PROJECT_FEATURES "none" CACHE STRING "Optional features: none, mpi, cuda, or all")
besa_feature(PROJECT_FEATURES VALUES "mpi;cuda" DESCRIPTION "Optional solver features")

# --------------------------------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------------------------------
# Header-only: cpdocs reads the interface usage requirements, so no compiled target is needed.
add_library(demo INTERFACE)
target_compile_features(demo INTERFACE cxx_std_20)
target_include_directories(demo INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

# The build system, not cpdocs, knows how a feature becomes a compile definition.
if(PROJECT_FEATURES_MPI)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_MPI=1)
endif()
if(PROJECT_FEATURES_CUDA)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_CUDA=1)
endif()

# --------------------------------------------------------------------------------------------------
# API documentation (only when cpdocs injects its adapter)
# --------------------------------------------------------------------------------------------------
if(COMMAND cpdocs_api)
  cpdocs_features(PROJECT_FEATURES)
  cpdocs_variant(serial PRIMARY PROJECT_FEATURES none)
  cpdocs_variant(mpi PROJECT_FEATURES mpi)
  cpdocs_variant(full PROJECT_FEATURES all)
  cpdocs_api(UNIT demo LANGUAGE cpp TARGET demo API include)
endif()
