# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(geom VERSION 2.0.0 LANGUAGES CXX)

include(cmake/feature.cmake)
set(PROJECT_FEATURES "none" CACHE STRING "Optional features: none, simd, or all")
besa_feature(PROJECT_FEATURES VALUES "simd" DESCRIPTION "Optional geometry features")

add_library(geom STATIC src/geom.cpp)
target_compile_features(geom PUBLIC cxx_std_20)
target_include_directories(geom PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(PROJECT_FEATURES_SIMD)
  target_compile_definitions(geom PUBLIC GEOM_HAVE_SIMD=1)
endif()

# One project, two documentation units: the C++ library and its Python bindings package.
if(COMMAND cpdocs_api)
  cpdocs_features(PROJECT_FEATURES)
  cpdocs_variant(portable PRIMARY PROJECT_FEATURES none)
  cpdocs_variant(simd PROJECT_FEATURES simd)
  cpdocs_api(UNIT geom LANGUAGE cpp TARGET geom API include)
  cpdocs_api(UNIT pygeom LANGUAGE python PACKAGE pygeom API python/pygeom)
endif()
