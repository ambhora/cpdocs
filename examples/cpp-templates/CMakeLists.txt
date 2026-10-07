# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(meta VERSION 0.4.0 LANGUAGES CXX)

add_library(meta INTERFACE)
target_compile_features(meta INTERFACE cxx_std_20)
target_include_directories(meta INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)

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
    "    \"id\": \"meta\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"]}\n"
    "  }]\n"
    "}\n")
endif()
