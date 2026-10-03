# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(demo-solver VERSION 1.2.0 LANGUAGES CXX)

set(PROJECT_FEATURES "none" CACHE STRING "Optional features: none, mpi, cuda, or all")
set(PROJECT_FEATURES_MPI FALSE)
set(PROJECT_FEATURES_CUDA FALSE)

if(CPDOCS_FEATURE_SET)
  file(READ "${CPDOCS_FEATURE_SET}" _cpdocs_selection)
  string(JSON _cpdocs_feature_count LENGTH "${_cpdocs_selection}" features)
  if(_cpdocs_feature_count GREATER 0)
    math(EXPR _cpdocs_last "${_cpdocs_feature_count} - 1")
    foreach(_index RANGE 0 ${_cpdocs_last})
      string(JSON _feature GET "${_cpdocs_selection}" features ${_index})
      if(_feature STREQUAL "mpi")
        set(PROJECT_FEATURES_MPI TRUE)
      elseif(_feature STREQUAL "cuda")
        set(PROJECT_FEATURES_CUDA TRUE)
      endif()
    endforeach()
  endif()
else()
  if(PROJECT_FEATURES STREQUAL "mpi" OR PROJECT_FEATURES STREQUAL "all")
    set(PROJECT_FEATURES_MPI TRUE)
  endif()
  if(PROJECT_FEATURES STREQUAL "cuda" OR PROJECT_FEATURES STREQUAL "all")
    set(PROJECT_FEATURES_CUDA TRUE)
  endif()
endif()

add_library(demo INTERFACE)
target_compile_features(demo INTERFACE cxx_std_20)
target_include_directories(demo INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
if(PROJECT_FEATURES_MPI)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_MPI=1)
endif()
if(PROJECT_FEATURES_CUDA)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_CUDA=1)
endif()

if(CPDOCS_FEATURE_SETS_OUTPUT)
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"generator\": \"CMake ${CMAKE_VERSION}\",\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [\n"
    "    {\"features\": []},\n"
    "    {\"features\": [\"mpi\"]},\n"
    "    {\"features\": [\"mpi\", \"cuda\"]}\n"
    "  ]\n"
    "}\n")
endif()

if(CPDOCS_FEATURE_SET AND CPDOCS_MANIFEST_OUTPUT)
  set(_defines "")
  if(PROJECT_FEATURES_MPI)
    list(APPEND _defines "\"DEMO_HAVE_MPI=1\"")
  endif()
  if(PROJECT_FEATURES_CUDA)
    list(APPEND _defines "\"DEMO_HAVE_CUDA=1\"")
  endif()
  string(JOIN ", " _defines_json ${_defines})
  file(WRITE "${CPDOCS_MANIFEST_OUTPUT}" "{\n"
    "  \"cpdocs-manifest\": 1,\n"
    "  \"units\": [{\n"
    "    \"id\": \"demo\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "      \"define\": [${_defines_json}]}\n"
    "  }]\n"
    "}\n")
endif()
