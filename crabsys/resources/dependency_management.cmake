
#############################################################################
##
## Dependency macros
##
#############################################################################

SET(LIBS_LINK_LIBS "")
SET(LIBS_INCLUDE_DIRS "")
SET(LIBS "")

IF(NOT dependency_macros_defined EQUAL 1)

    SET(dependency_macros_defined 1)

    macro(_append_lib_info PREFIX DEP_NAME)
        LIST(APPEND ${PREFIX}_LIBS_INCLUDE_DIRS ${${DEP_NAME}_INCLUDE_DIRS})

        LIST(APPEND ${PREFIX}_LIBS_LINK_LIBS ${${DEP_NAME}_LINK_LIBS})

        LIST(APPEND ${PREFIX}_LIBS ${DEP_NAME})
    endmacro(_append_lib_info)


    ########################################################################
    # Includes a library - low level macro
    macro(include_lib_macro_internal LIB_SEARCH_DIR PREFIX DEP_NAME)
        LIST(FIND CURRENT_LIBS "${DEP_NAME}" contains_lib)

        IF(contains_lib EQUAL -1)
            SET(PREVIOUS_DO_EXPORT_VALUE ${DO_EXPORT})
            SET(DO_EXPORT 1)

            add_subdirectory(${LIB_SEARCH_DIR} ${LIB_SEARCH_DIR})

            SET(DO_EXPORT ${PREVIOUS_DO_EXPORT_VALUE})
        ENDIF()

        _append_lib_info(${PREFIX} ${DEP_NAME})

    endmacro(include_lib_macro_internal)
    ########################################################################



    ########################################################################
    # Exports a library
    macro(export_lib_macro DEP_NAME)
        LIST(APPEND ${DEP_NAME}_LIB_INCLUDE_DIRS ${${DEP_NAME}_INCLUDE_DIRS})
        LIST(APPEND ${DEP_NAME}_LIB_INCLUDE_DIRS ${${DEP_NAME}_LIBS_INCLUDE_DIRS})

        LIST(APPEND ${DEP_NAME}_LIB_LINK_LIBS ${${DEP_NAME}_LIB})
        LIST(APPEND ${DEP_NAME}_LIB_LINK_LIBS ${${DEP_NAME}_LIBS_LINK_LIBS})

        LIST(APPEND CURRENT_LIBS ${DEP_NAME})

        # Set everything locally
        SET(${DEP_NAME}_INCLUDE_DIRS ${${DEP_NAME}_LIB_INCLUDE_DIRS})
        SET(${DEP_NAME}_LINK_LIBS ${${DEP_NAME}_LIB_LINK_LIBS})

        foreach(f ${LIBS})
            SET(${f}_INCLUDE_DIRS ${${f}_INCLUDE_DIRS})
            SET(${f}_LINK_LIBS ${${f}_LINK_LIBS})
        endforeach(f)

        SET(CURRENT_LIBS ${CURRENT_LIBS})

        # Set everything in parent scope
        IF( DEFINED DO_EXPORT )
            SET(${DEP_NAME}_INCLUDE_DIRS ${${DEP_NAME}_LIB_INCLUDE_DIRS} PARENT_SCOPE)
            SET(${DEP_NAME}_LINK_LIBS ${${DEP_NAME}_LIB_LINK_LIBS} PARENT_SCOPE)

            foreach(f ${LIBS})
                SET(${f}_INCLUDE_DIRS ${${f}_INCLUDE_DIRS} PARENT_SCOPE)
                SET(${f}_LINK_LIBS ${${f}_LINK_LIBS} PARENT_SCOPE)
            endforeach(f)

            SET(CURRENT_LIBS ${CURRENT_LIBS} PARENT_SCOPE)
        ENDIF()
    endmacro(export_lib_macro)
    ########################################################################

ENDIF()

#############################################################################
