# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(ring VERSION 0.1.0 LANGUAGES C)

add_library(ring STATIC src/ring.c)
target_compile_features(ring PUBLIC c_std_11)
target_include_directories(ring PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

if(CPDOCS_FEATURE_SETS_OUTPUT)
  file(WRITE "${CPDOCS_FEATURE_SETS_OUTPUT}" "{\n"
    "  \"cpdocs-feature-sets\": 1,\n"
    "  \"generator\": \"CMake ${CMAKE_VERSION}\",\n"
    "  \"project\": {\"name\": \"${PROJECT_NAME}\", \"version\": \"${PROJECT_VERSION}\"},\n"
    "  \"feature-sets\": [{\"features\": []}]\n"
    "}\n")
endif()

if(CPDOCS_FEATURE_SET AND CPDOCS_MANIFEST_OUTPUT)
  file(WRITE "${CPDOCS_MANIFEST_OUTPUT}" "{\n"
    "  \"cpdocs-manifest\": 1,\n"
    "  \"units\": [{\n"
    "    \"id\": \"ring\", \"language\": \"c\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "    \"parse\": {\"language\": \"c\", \"standard\": \"c11\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"]}\n"
    "  }]\n"
    "}\n")
endif()
