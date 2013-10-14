
cmake_minimum_required(VERSION 2.8)

set(CMAKE_MODULE_PATH ${{CMAKE_MODULE_PATH}} "{module_dir}")
include(dependency_management)

project ({project_name})

{targets}
