# --------------------------------------------------------------------------------------------------
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: (C) 2024 Jayesh Badwaik <j.badwaik@fz-juelich.de>
# --------------------------------------------------------------------------------------------------
include_guard(GLOBAL)

function(besa_feature_internal_check_validity FEATURE_NAME)
  set(FEATURE_VALUE ${${FEATURE_NAME}})

  foreach(FEATURE ${FEATURE_VALUE})
    if(NOT ${FEATURE} IN_LIST ${FEATURE_NAME}_ARRAY)
      message(
        FATAL_ERROR
        "
        Invalid ${FEATURE_NAME} Feature ${FEATURE}.
        Valid values are: none,${${FEATURE_NAME}_ARRAY},all
        "
        )
    endif()
  endforeach()
endfunction()

function(besa_feature_help)
  message("Incorrect Usage of besa_feature. Correct Usage is:")
  message(
    FATAL_ERROR
    "
    besa_feature(
      <NAME>
      VALUES <ARRAY_OF_SUPPORTED_VALUES>
      DESCRIPTION <DESCRIPTION>
      )
    "
    )
endfunction()

function(
    besa_feature
    FEATURE_NAME
    VALUES_NAME FEATURE_ARRAY
    DESCRIPTION_NAME DESCRIPTION_STRING
    )

  if(NOT (${VALUES_NAME} STREQUAL "VALUES"))
    besa_feature_help()
  endif()

  if(NOT (${DESCRIPTION_NAME} STREQUAL "DESCRIPTION"))
    besa_feature_help()
  endif()


  set(${FEATURE_NAME} ${${FEATURE_NAME}} PARENT_SCOPE)

  set(${FEATURE_NAME}_ARRAY ${FEATURE_ARRAY})
  set(${FEATURE_NAME}_ARRAY ${${FEATURE_NAME}_ARRAY} PARENT_SCOPE)

  if("none" IN_LIST ${FEATURE_NAME})

    list(LENGTH ${FEATURE_NAME} FEATURE_LENGTH)
    if(NOT (${FEATURE_LENGTH} EQUAL 1))
      message(
        FATAL_ERROR
        "
        none is mutually exclusive with other ${FEATURE_NAME} features.
        "
        )

    endif()

  elseif("all" IN_LIST ${FEATURE_NAME})

    list(LENGTH ${FEATURE_NAME} FEATURE_LENGTH)
    if(NOT (${FEATURE_LENGTH} EQUAL 1))

      message(
        FATAL_ERROR
        "
        all is mutually exclusive with other ${FEATURE_NAME} features.
        "
        )
    endif()

    foreach(FEATURE ${FEATURE_ARRAY})
      string(TOUPPER ${FEATURE} FEATURE_UPPER)
      string(REPLACE "-" "_" FEATURE_UPPER ${FEATURE_UPPER})
      set(FEATURE_VARIABLE ${FEATURE_NAME}_${FEATURE_UPPER})
      set(${FEATURE_VARIABLE} TRUE PARENT_SCOPE)
    endforeach()

  else()
    besa_feature_internal_check_validity(${FEATURE_NAME})

    foreach(FEATURE ${FEATURE_ARRAY})
      string(TOUPPER ${FEATURE} FEATURE_UPPER)
      string(REPLACE "-" "_" FEATURE_UPPER ${FEATURE_UPPER})
      set(FEATURE_VARIABLE ${FEATURE_NAME}_${FEATURE_UPPER})
      set(${FEATURE_VARIABLE} FALSE PARENT_SCOPE)
    endforeach()

    foreach(FEATURE ${${FEATURE_NAME}})
      string(TOUPPER ${FEATURE} FEATURE_UPPER)
      string(REPLACE "-" "_" FEATURE_UPPER ${FEATURE_UPPER})
      set(FEATURE_VARIABLE ${FEATURE_NAME}_${FEATURE_UPPER})
      set(${FEATURE_VARIABLE} TRUE PARENT_SCOPE)
    endforeach()
  endif()

endfunction()
