# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.20)
project(cpdocs-cxx-standards VERSION 1.0.0 LANGUAGES CXX)

# Both the ordinary project build and the manifest parser use this exact standard.
# The cpdocs configuration passes the desired value using {{cxx.standard}}.
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
if(NOT CMAKE_CXX_STANDARD MATCHES "^(17|20|23)$")
  message(FATAL_ERROR "This example supports C++17, C++20, and C++23")
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(cpdocs_standard_demo STATIC src/standard_demo.cpp)
target_compile_features(cpdocs_standard_demo PUBLIC cxx_std_${CMAKE_CXX_STANDARD})
target_include_directories(cpdocs_standard_demo PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

# The same generic JSON contract is used for every C++ standard.
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
    "    \"id\": \"cpdocs_standard_demo\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++${CMAKE_CXX_STANDARD}\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"]}\n"
    "  }]\n"
    "}\n")
endif()
