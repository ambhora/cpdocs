# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(cpdocs-basic-example VERSION 1.0.0 LANGUAGES CXX)

add_library(acme_math STATIC src/math.cpp)
target_compile_features(acme_math PUBLIC cxx_std_20)
target_include_directories(acme_math PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

# cpdocs contract provider.  This is ordinary project code: cpdocs does not inject CMake functions.
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
    "    \"id\": \"acme_math\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\"]}\n"
    "  }]\n"
    "}\n")
endif()
