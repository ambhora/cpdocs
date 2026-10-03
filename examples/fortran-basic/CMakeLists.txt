# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(fortran_geometry VERSION 1.0.0 LANGUAGES NONE)

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
    "    \"id\": \"geometry\", \"language\": \"fortran\",\n"
    "    \"modules\": [\"${CMAKE_CURRENT_SOURCE_DIR}/mod\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/lib\"]\n"
    "  }]\n"
    "}\n")
endif()
