
cmake_minimum_required(VERSION 2.8)

set(CMAKE_MODULE_PATH ${{CMAKE_MODULE_PATH}} "{module_dir}")
include(dependency_management)

project ({project_name})

set(CMAKE_CXX_FLAGS "{cpp_flags}")

{dependencies}

set ({project_name}_INCLUDE_DIRS
    {include_dirs}
)

set({project_name}_SRCS
    {sources}
)

include_directories(${{{project_name}_INCLUDE_DIRS}})
include_directories(${{LIBS_INCLUDE_DIRS}})

{executables}

{libraries}

export_lib_macro("${{{project_name}_INCLUDE_DIRS}}" "${{{project_name}_LIBS}}")
