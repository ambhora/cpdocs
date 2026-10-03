# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(geom VERSION 2.0.0 LANGUAGES CXX)

set(PROJECT_FEATURES "none" CACHE STRING "Optional features: none or simd")
set(PROJECT_FEATURES_SIMD FALSE)
if(CPDOCS_FEATURE_SET)
  file(READ "${CPDOCS_FEATURE_SET}" _cpdocs_selection)
  string(JSON _cpdocs_feature_count LENGTH "${_cpdocs_selection}" features)
  if(_cpdocs_feature_count GREATER 0)
    math(EXPR _cpdocs_last "${_cpdocs_feature_count} - 1")
    foreach(_index RANGE 0 ${_cpdocs_last})
      string(JSON _feature GET "${_cpdocs_selection}" features ${_index})
      if(_feature STREQUAL "simd")
        set(PROJECT_FEATURES_SIMD TRUE)
      endif()
    endforeach()
  endif()
elseif(PROJECT_FEATURES STREQUAL "simd" OR PROJECT_FEATURES STREQUAL "all")
  set(PROJECT_FEATURES_SIMD TRUE)
endif()

add_library(geom STATIC src/geom.cpp)
target_compile_features(geom PUBLIC cxx_std_20)
target_include_directories(geom PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(PROJECT_FEATURES_SIMD)
  target_compile_definitions(geom PUBLIC GEOM_HAVE_SIMD=1)
endif()

if(CPDOCS_FEATURE_SETS_OUTPUT)
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"generator\": \"CMake ${CMAKE_VERSION}\",\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [{\"features\": []}, {\"features\": [\"simd\"]}]\n"
    "}\n")
endif()

if(CPDOCS_FEATURE_SET AND CPDOCS_MANIFEST_OUTPUT)
  set(_defines "")
  if(PROJECT_FEATURES_SIMD)
    list(APPEND _defines "\"GEOM_HAVE_SIMD=1\"")
  endif()
  string(JOIN ", " _defines_json ${_defines})
  file(WRITE "${CPDOCS_MANIFEST_OUTPUT}" "{\n"
    "  \"cpdocs-manifest\": 1,\n"
    "  \"units\": [\n"
    "    {\"id\": \"geom\", \"language\": \"cpp\",\n"
    "     \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "     \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "     \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "     \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "       \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"], \"define\": [${_defines_json}]}},\n"
    "    {\"id\": \"pygeom\", \"language\": \"python\", \"package\": \"pygeom\",\n"
    "     \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/python/pygeom\"}]}\n"
    "  ]\n"
    "}\n")
endif()
