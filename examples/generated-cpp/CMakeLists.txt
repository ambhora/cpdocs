# --------------------------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2026 cpdocs developers
# SPDX-License-Identifier: Apache-2.0
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.24)
project(cpdocs-generated-example VERSION 1.0.0 LANGUAGES CXX)

set(GENERATED_INCLUDE ${CMAKE_BINARY_DIR}/generated/include)
set(GENERATED_HEADER ${GENERATED_INCLUDE}/acme/generated.hpp)
add_custom_command(
  OUTPUT ${GENERATED_HEADER}
  COMMAND ${CMAKE_COMMAND} -E make_directory ${GENERATED_INCLUDE}/acme
  COMMAND ${CMAKE_COMMAND} -E copy
    ${CMAKE_CURRENT_SOURCE_DIR}/generated-template/generated.hpp ${GENERATED_HEADER}
  DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/generated-template/generated.hpp
  VERBATIM
)
add_custom_target(generate-api-header DEPENDS ${GENERATED_HEADER})

add_library(acme_generated STATIC src/generated.cpp)
target_compile_features(acme_generated PUBLIC cxx_std_20)
target_include_directories(acme_generated PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include ${GENERATED_INCLUDE})
add_dependencies(acme_generated generate-api-header)

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
    "    \"id\": \"acme_generated\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}, "
      "{\"path\": \"${GENERATED_INCLUDE}\", \"generated\": true}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\", \"${GENERATED_INCLUDE}\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\", \"${GENERATED_INCLUDE}\"]}\n"
    "  }]\n"
    "}\n")
endif()
