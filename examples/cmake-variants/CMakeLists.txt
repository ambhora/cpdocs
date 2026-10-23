# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
# A plain CMake project with a variant space and the two cpdocs hooks.
#
# The project has exactly one implementation, host or gpu, and MPI optionally. That gives four
# variants: host, host + mpi, gpu and gpu + mpi. A normal build selects one with DEMO_FEATURES; cpdocs
# asks for the list of variants and then builds each of them.
cmake_minimum_required(VERSION 4.3)
project(demo-variants VERSION 1.0.0 LANGUAGES CXX)

# --------------------------------------------------------------------------------------------------
# Variant space
# --------------------------------------------------------------------------------------------------
# One value of each axis makes a variant; "none" on the parallel axis selects no feature.
set(DEMO_IMPLEMENTATIONS host gpu)
set(DEMO_PARALLEL none mpi)
set(DEMO_FEATURES "host" CACHE STRING "Features of the build: host or gpu, optionally with mpi")

# --------------------------------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------------------------------
# cpdocs passes the selected variant as a JSON file; a normal build uses DEMO_FEATURES.
set(_features ${DEMO_FEATURES})
if(CPDOCS_FEATURE_SET)
  file(READ "${CPDOCS_FEATURE_SET}" _selection)
  string(JSON _count LENGTH "${_selection}" features)
  set(_features "")
  if(_count GREATER 0)
    math(EXPR _last "${_count} - 1")
    foreach(_index RANGE 0 ${_last})
      string(JSON _feature GET "${_selection}" features ${_index})
      list(APPEND _features "${_feature}")
    endforeach()
  endif()
endif()

set(_implementation "")
foreach(_feature IN LISTS _features)
  if(_feature IN_LIST DEMO_IMPLEMENTATIONS)
    if(_implementation)
      message(FATAL_ERROR "choose one implementation of ${DEMO_IMPLEMENTATIONS}, not ${_features}")
    endif()
    set(_implementation "${_feature}")
  elseif(NOT _feature IN_LIST DEMO_PARALLEL)
    message(FATAL_ERROR "unknown feature ${_feature}")
  endif()
endforeach()
if(NOT _implementation)
  message(FATAL_ERROR "choose one implementation of ${DEMO_IMPLEMENTATIONS}")
endif()
set(DEMO_WITH_GPU OFF)
set(DEMO_WITH_MPI OFF)
if(_implementation STREQUAL "gpu")
  set(DEMO_WITH_GPU ON)
endif()
if("mpi" IN_LIST _features)
  set(DEMO_WITH_MPI ON)
endif()

# --------------------------------------------------------------------------------------------------
# Targets
# --------------------------------------------------------------------------------------------------
add_library(demo INTERFACE)
target_compile_features(demo INTERFACE cxx_std_20)
target_include_directories(demo INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
if(DEMO_WITH_MPI)
  target_compile_definitions(demo INTERFACE DEMO_HAVE_MPI=1)
endif()
if(DEMO_WITH_GPU)
  target_include_directories(demo INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/device/include>)
endif()

# --------------------------------------------------------------------------------------------------
# cpdocs hooks
# --------------------------------------------------------------------------------------------------
# First hook: list every variant as the product of the two axes.
if(CPDOCS_FEATURE_SETS_OUTPUT)
  set(_variants "")
  foreach(_implementation_value IN LISTS DEMO_IMPLEMENTATIONS)
    foreach(_parallel_value IN LISTS DEMO_PARALLEL)
      if(_parallel_value STREQUAL "none")
        list(APPEND _variants "{\"features\": [\"${_implementation_value}\"]}")
      else()
        list(APPEND _variants "{\"features\": [\"${_implementation_value}\", \"${_parallel_value}\"]}")
      endif()
    endforeach()
  endforeach()
  string(JOIN ",\n    " _variants_json ${_variants})
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"generator\": \"CMake ${CMAKE_VERSION}\",\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [\n    ${_variants_json}\n  ]\n"
    "}\n")
endif()

# Second hook: describe the selected variant. The C++ unit exists in every variant; the GPU
# implementation adds a CUDA unit, parsed by Clang as C++ but documented as CUDA.
if(CPDOCS_FEATURE_SET AND CPDOCS_MANIFEST_OUTPUT)
  set(_defines "")
  if(DEMO_WITH_MPI)
    set(_defines "\"DEMO_HAVE_MPI=1\"")
  endif()
  string(CONCAT _units "{\n"
    "    \"id\": \"core\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"], \"define\": [${_defines}]}\n"
    "  }")
  if(DEMO_WITH_GPU)
    string(APPEND _units ", {\n"
      "    \"id\": \"device\", \"language\": \"cuda\",\n"
      "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/device/include\"}],\n"
      "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
      "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\", \"${CMAKE_CURRENT_SOURCE_DIR}/device/include\"],\n"
      "      \"define\": [${_defines}]}\n"
      "  }")
  endif()
  file(WRITE "${CPDOCS_MANIFEST_OUTPUT}" "{\n  \"cpdocs-manifest\": 1,\n  \"units\": [${_units}]\n}\n")
endif()
