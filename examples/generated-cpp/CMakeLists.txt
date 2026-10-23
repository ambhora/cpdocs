# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 cpdocs developers
# --------------------------------------------------------------------------------------------------
cmake_minimum_required(VERSION 4.3)
project(cpdocs-generated-example VERSION 1.0.0 LANGUAGES CXX)

# The public API consists of the checked-in header include/acme/core.hpp and two headers the build
# generates into the build directory. Neither generated header is checked in, and neither exists
# until the build has run.
set(ACME_GENERATED_INCLUDE ${CMAKE_CURRENT_BINARY_DIR}/generated/include)

# Configure time: acme/version.hpp from a template and the version given to project().
configure_file(cmake/version.hpp.in ${ACME_GENERATED_INCLUDE}/acme/version.hpp @ONLY)

# Build time: acme/status.hpp from the status table, by a generator script.
set(ACME_STATUS_HEADER ${ACME_GENERATED_INCLUDE}/acme/status.hpp)
add_custom_command(
  OUTPUT ${ACME_STATUS_HEADER}
  COMMAND ${CMAKE_COMMAND}
    -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/data/status-codes.txt
    -DOUTPUT=${ACME_STATUS_HEADER}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/generate-status.cmake
  DEPENDS data/status-codes.txt cmake/generate-status.cmake
  COMMENT "Generating acme/status.hpp"
  VERBATIM
)
add_custom_target(acme-generated-headers DEPENDS ${ACME_STATUS_HEADER})

add_library(acme STATIC src/core.cpp)
target_compile_features(acme PUBLIC cxx_std_20)
target_include_directories(acme PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include ${ACME_GENERATED_INCLUDE})
add_dependencies(acme acme-generated-headers)

# cpdocs hooks. The manifest names the generated directory as an API root marked generated; the
# build hook in docs/cpdocs.yml builds acme-generated-headers before cpdocs reads it.
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
    "    \"id\": \"acme\", \"language\": \"cpp\",\n"
    "    \"api\": [{\"path\": \"${CMAKE_CURRENT_SOURCE_DIR}/include\"}, "
      "{\"path\": \"${ACME_GENERATED_INCLUDE}\", \"generated\": true}],\n"
    "    \"headers\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\", \"${ACME_GENERATED_INCLUDE}\"],\n"
    "    \"sources\": [\"${CMAKE_CURRENT_SOURCE_DIR}/src\"],\n"
    "    \"parse\": {\"language\": \"cpp\", \"standard\": \"c++20\",\n"
    "      \"include\": [\"${CMAKE_CURRENT_SOURCE_DIR}/include\", \"${ACME_GENERATED_INCLUDE}\"]}\n"
    "  }]\n"
    "}\n")
endif()
