
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

    macro(_append_lib_info LIBNAME LIB_DIR_NAME)
        foreach(f ${${LIBNAME}_INCLUDE_DIRS})
            LIST(APPEND LIBS_INCLUDE_DIRS ${f})
        endforeach(f)

        LIST(APPEND LIBS_LINK_LIBS ${${LIBNAME}_LINK_LIBS})

        LIST(APPEND LIBS ${LIBNAME})

        SET(${LIBNAME}_LIB_DIR_NAME ${LIB_DIR_NAME})
    endmacro(_append_lib_info)


    ########################################################################
    # Includes a library - low level macro
    macro(include_lib_macro_internal LIB_SEARCH_DIR LIB_BINARY_DIR)
        get_filename_component(lib_dir_name ${LIB_SEARCH_DIR} NAME)

        LIST(FIND CURRENT_LIBS "${lib_dir_name}" contains_lib)

        IF(contains_lib EQUAL -1)
            SET(PREVIOUS_DO_EXPORT_VALUE ${DO_EXPORT})
            SET(DO_EXPORT 1)

            IF ( ${LIB_BINARY_DIR} EQUAL -1 )
                add_subdirectory(${LIB_SEARCH_DIR})
            ELSE()
                add_subdirectory(${LIB_SEARCH_DIR} ${LIB_BINARY_DIR})
            ENDIF()

            _append_lib_info(${EXPORTED_LIB_NAME} ${lib_dir_name})

            SET(DO_EXPORT ${PREVIOUS_DO_EXPORT_VALUE})
        ELSE()
            _append_lib_info(${${lib_dir_name}_LIBNAME} ${lib_dir_name})
        ENDIF()

    endmacro(include_lib_macro_internal)
    ########################################################################



    ########################################################################
    # Exports a library
    macro(export_lib_macro INCLUDE_DIRS LINK_LIBS)
        IF( DEFINED DO_EXPORT )
            SET(LIBNAME ${PROJECT_NAME})

            LIST(APPEND LIB_INCLUDE_DIRS ${INCLUDE_DIRS})
            LIST(APPEND LIB_INCLUDE_DIRS ${LIBS_INCLUDE_DIRS})

            LIST(APPEND LIB_LINK_LIBS ${LINK_LIBS})
            LIST(APPEND LIB_LINK_LIBS ${LIBS_LINK_LIBS})

            SET(${LIBNAME}_INCLUDE_DIRS ${LIB_INCLUDE_DIRS} PARENT_SCOPE)
            SET(${LIBNAME}_LINK_LIBS ${LIB_LINK_LIBS} PARENT_SCOPE)
            SET(EXPORTED_LIB_NAME ${LIBNAME} PARENT_SCOPE)

            foreach(f ${LIBS})
                SET(${f}_INCLUDE_DIRS ${${f}_INCLUDE_DIRS} PARENT_SCOPE)
                SET(${f}_LINK_LIBS ${${f}_LINK_LIBS} PARENT_SCOPE)
                SET(${${f}_LIB_DIR_NAME}_LIBNAME ${f} PARENT_SCOPE)
            endforeach(f)

            get_filename_component(lib_dir_name ${CMAKE_CURRENT_LIST_DIR} NAME)
            LIST(APPEND CURRENT_LIBS ${lib_dir_name})
            SET(CURRENT_LIBS ${CURRENT_LIBS} PARENT_SCOPE)

            SET(${lib_dir_name}_LIBNAME ${LIBNAME} PARENT_SCOPE)
        ENDIF()
    endmacro(export_lib_macro)
    ########################################################################



    ########################################################################
    # Higher level library include macros
    macro(include_lib_macro LIB_DIR)
        include_lib_macro_internal(${LIB_DIR} -1)
    endmacro(include_lib_macro)

    macro(include_external_lib_macro SEARCH_DIR BINARY_DIR)
        include_lib_macro_internal(${SEARCH_DIR} ${BINARY_DIR})
    endmacro(include_external_lib_macro)
    ########################################################################



    ########################################################################
    # Include library from repository URL
    macro(include_repo_lib_macro REPO_URL)
        execute_process(COMMAND python -c "import sys; import re; sys.stdout.write(re.match('^.*\\/(.*)\\.git', '${REPO_URL}').group(1))"
                        OUTPUT_VARIABLE REPO_NAME)

        LIST(FIND CURRENT_LIBS "${REPO_NAME}" contains_lib)

        IF(contains_lib EQUAL -1)

            if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/libs/${REPO_NAME})
                if(IS_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/libs/${REPO_NAME})
                    execute_process(COMMAND git status
                                    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/libs/${REPO_NAME}
                                    RESULT_VARIABLE GIT_STATUS)

                    if( ${GIT_STATUS} EQUAL 0 )
                        include_lib_macro("libs/${REPO_NAME}")
                    else()
                        MESSAGE( FATAL_ERROR "libs/${REPO_NAME} exists but it isn't a git repo!" )
                    endif()
                else()
                    MESSAGE( FATAL_ERROR "libs/${REPO_NAME} already exists but it isn't a directory!" )
                endif()
            else()
                file(MAKE_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/libs)

                execute_process(COMMAND git clone ${REPO_URL}
                                WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/libs
                                RESULT_VARIABLE GIT_CLONE_RESULT)

                if( ${GIT_CLONE_RESULT} EQUAL 0 )
                    include_lib_macro("libs/${REPO_NAME}")
                else()
                    MESSAGE( FATAL_ERROR "Couldn't clone repository ${REPO_URL}" )
                endif()
            endif()

        ELSE()
            _append_lib_info(${${REPO_NAME}_LIBNAME} ${REPO_NAME})
        ENDIF()
    endmacro(include_repo_lib_macro)
    ########################################################################

ENDIF()

#############################################################################
