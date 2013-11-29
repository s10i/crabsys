
cmake_output_variables = {
    "name": "__crabsys_target_name=",
    "location": "__crabsys_target_location="
}

#############################################################################
## Templates ##
###############
executable_template = ''+\
    'add_executable({name} ${{{name}_SRCS}} {sources_lists})\n'+\
    'target_link_libraries({name} ${{{name}_LIBS_LINK_LIBS}} {cmake_libraries})\n'+\
    'set_target_properties({name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY '+\
        '{target_path})\n'+\
    'set_target_properties({name} PROPERTIES COMPILE_FLAGS "{compile_flags}")\n'+\
    'set_target_properties({name} PROPERTIES LINK_FLAGS "{link_flags}")\n'+\
    'IF(${{CMAKE_SYSTEM_NAME}} MATCHES "Darwin")\n'+\
    '   set_target_properties({name} PROPERTIES INSTALL_RPATH "@loader_path/.")\n'+\
    '   set_target_properties({name} PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE)\n'+\
    'ENDIF()\n'+\
    'IF(${{CMAKE_SYSTEM_NAME}} MATCHES "Linux")\n'+\
    '   IF( NOT( "{linux_rpath}" STREQUAL "" ) )\n'+\
    '      set_target_properties({name} PROPERTIES INSTALL_RPATH "{linux_rpath}")\n'+\
    '      set_target_properties({name} PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE)\n'+\
    '   ENDIF()\n'+\
    'ENDIF()\n'+\
    'get_target_property(__crabsys_target_{name}_location {name} LOCATION)\n'+\
    'MESSAGE("' + cmake_output_variables["name"] + '{name}")\n'+\
    'MESSAGE("' + cmake_output_variables["location"] + '${{__crabsys_target_{name}_location}}")\n'

library_template = ''+\
    'add_library({name} ${{{name}_SRCS}} {sources_lists})\n'+\
    'target_link_libraries({name} ${{{name}_LIBS_LINK_LIBS}} {cmake_libraries})\n'+\
    'set_target_properties({name} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY '+\
        '{target_path})\n'+\
    'set_target_properties({name} PROPERTIES COMPILE_FLAGS "{compile_flags}")\n'+\
    'set_target_properties({name} PROPERTIES LINK_FLAGS "{link_flags}")\n'+\
    'set({name}_LIB {name})\n'+\
    'get_target_property(__crabsys_target_{name}_location {name} LOCATION)\n'+\
    'MESSAGE("' + cmake_output_variables["name"] + '{name}")\n'+\
    'MESSAGE("' + cmake_output_variables["location"] + '${{__crabsys_target_{name}_location}}")\n'

export_template = ''+\
    'export_lib_macro({name})\n'

sources_template = ''+\
    'set({name}_SRCS {sources})\n'

target_includes_variable_template = ''+\
    'set({name}_INCLUDE_DIRS {sources})\n'

target_includes_template = ''+\
    'include_directories(${{{name}_INCLUDE_DIRS}})\n'+\
    'include_directories(${{{name}_LIBS_INCLUDE_DIRS}})\n'

repository_dependency_template = ''+\
    'include_repo_lib_macro({repository_url})\n'

path_dependency_template = ''+\
    'include_lib_macro_internal({build_path} {prefix} {name})\n'

custom_dependency_template = ''+\
    'LIST(APPEND {name}_INCLUDE_DIRS {includes})\n'+\
    'LIST(APPEND {name}_LINK_LIBS {libs})\n'+\
    '_append_lib_info({prefix} {name})\n'

cmake_dependency_template = ''+\
    'find_package({name} REQUIRED)\n'+\
    'LIST(APPEND __CRABSYS_CMAKE_DEP_{name}_INCLUDE_DIRS ${{{upper_name}_INCLUDE_DIR}})\n'+\
    'LIST(APPEND __CRABSYS_CMAKE_DEP_{name}_LINK_LIBS ${{{upper_name}_LIBRARIES}})\n'+\
    '_append_lib_info({prefix} __CRABSYS_CMAKE_DEP_{name})\n'

cmake_dependency_search_path_template = ''+\
    'set(CMAKE_MODULE_PATH ${{CMAKE_MODULE_PATH}} "{search_path}")\n'

dependencies_post_processing_template = ''+\
    'add_custom_command(TARGET {target} PRE_BUILD\n'+\
    '                   COMMAND ${{CMAKE_COMMAND}} -E make_directory {libs_path})\n'+\
    'add_custom_command(TARGET {target} PRE_BUILD\n'+\
    '                   COMMAND ${{CMAKE_COMMAND}} -E copy {lib_original_path} {lib_destination_path})\n'+\
    'IF(${{CMAKE_SYSTEM_NAME}} MATCHES "Darwin")\n'+\
    '   add_custom_command(TARGET {target} PRE_BUILD\n'+\
    '                      COMMAND install_name_tool -id {lib_id} {lib_original_path})\n'+\
    '   add_custom_command(TARGET {target} PRE_BUILD\n'+\
    '                      COMMAND install_name_tool -id {lib_id} {lib_destination_path})\n'+\
    'ENDIF()\n'
#############################################################################
