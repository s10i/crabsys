#!/usr/bin/env python

import json
import os
import os.path
import sys
import subprocess

resources_dir = os.path.dirname(os.path.realpath(__file__)) + '/resources'
build_folder_relative_path = 'build/.build'
targets_relative_path = 'build/'


class Context:
    def __init__(self, build_info, current_dir, parent_context):
        self.build_info = build_info
        self.current_dir = current_dir
        self.parent_context = parent_context

def get_file_content(file_path):
    file_handle = open(file_path, 'r')
    content = file_handle.read()
    file_handle.close()
    return content




#############################################################################
## Templates ##
###############
executable_template = ''+\
    'add_executable({name} ${{{project_name}_SRCS}})\n'+\
    'target_link_libraries({name} ${{LIBS_LINK_LIBS}})\n'+\
    'set_target_properties({name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY '+\
        '{target_path})\n'

library_template = ''+\
    'add_library({name} ${{{project_name}_SRCS}})\n'+\
    'target_link_libraries({name} ${{LIBS_LINK_LIBS}})\n'+\
    'LIST(APPEND {project_name}_LIBS {name})\n'+\
    'set_target_properties({name} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY '+\
        '{target_path})\n'

repository_dependency_template = ''+\
    'include_repo_lib_macro({repository_url})\n'

path_dependency_template = ''+\
    'include_lib_macro_internal({build_path} {build_path})\n'

def init_templates():
    templates_dir = resources_dir + '/templates'

    global cmake_file_template
    cmake_file_template = get_file_content(templates_dir+"/CMakeLists.txt")
#############################################################################



#############################################################################
## Dependencies ##
##################
def process_repository_dependency(dependency_info, context):
    return repository_dependency_template.format(
        repository_url=dependency_info['repository']
    )

    return path_dependency_template.format(
        build_path=dependency_build_folder_path
    )

def process_path_dependency(dependency_info, context):
    dependency_absolute_path = os.path.abspath(context.current_dir + '/' +\
        dependency_info['path'])

    process(dependency_absolute_path, context)

    dependency_build_folder_path = dependency_absolute_path + '/' +\
        build_folder_relative_path

    return path_dependency_template.format(
        build_path=dependency_build_folder_path
    )

def process_dependency(dependency_info, context):
    if 'repository' in dependency_info:
        return process_repository_dependency(dependency_info, context)
    elif 'path' in dependency_info:
        return process_path_dependency(dependency_info, context)

    return ''

def process_dependencies(context):
    dependencies_includes = ''
    if 'dependencies' in context.build_info:
        for dependency in context.build_info['dependencies']:
            dependencies_includes += process_dependency(dependency, context)
    return dependencies_includes
#############################################################################



#############################################################################
## Executables ##
#################
def process_executable(executable_info, context):
    return executable_template.format(
        name=executable_info['name'],
        target_path=context.current_dir+'/'+targets_relative_path,
        project_name=context.build_info['project_name']
    )

def process_executables(context):
    executables_definitions = ''
    if 'executables' in context.build_info:
        for executable in context.build_info['executables']:
            executables_definitions += process_executable(executable, context)
    return executables_definitions
#############################################################################



#############################################################################
## Libraries ##
###############
def process_library(library_info, context):
    return library_template.format(
        name=library_info['name'],
        target_path=context.current_dir+'/'+targets_relative_path,
        project_name=context.build_info['project_name']
    )

def process_libraries(context):
    libraries_definitions = ''
    if 'libraries' in context.build_info:
        for library in context.build_info['libraries']:
            libraries_definitions += process_library(library, context)
    return libraries_definitions
#############################################################################



#############################################################################
## Sources ##
#############
def process_sources(context):
    return '\n'.join(
        [context.current_dir+"/"+source
         for source in context.build_info['sources']]
    )
#############################################################################



#############################################################################
## Includes ##
#############
def process_includes(context):
    return '\n'.join(
        [context.current_dir+"/"+include_dir
         for include_dir in context.build_info['includes']]
    )
#############################################################################



#############################################################################
def process(current_dir, parent_context=None):
    build_folder = current_dir+'/'+build_folder_relative_path
    cmake_lists_file_path = build_folder +'/CMakeLists.txt'
    crab_file_path = current_dir+'/crab.json'

    try:
        cmake_file_last_modification = os.stat(cmake_lists_file_path).st_mtime
        crab_file_last_modification = os.stat(crab_file_path).st_mtime

        if crab_file_last_modification < cmake_file_last_modification:
            return
    except OSError, e:
        pass

    # Read crab file and parse as json
    build_info = json.loads(get_file_content(crab_file_path))

    context = Context(build_info, current_dir, parent_context)

    if 'cpp_flags' not in build_info:
        build_info['cpp_flags'] = ''
    if 'includes' not in build_info:
        build_info['includes'] = ''
    if 'project_name' not in build_info:
        print crab_file_path + ': project name not defined, using folder name'
        build_info['project_name'] =\
            os.path.basename(os.path.dirname(crab_file_path))

    dependencies_includes = process_dependencies(context)
    executables_definitions = process_executables(context)
    libraries_definitions = process_libraries(context)
    source_files_list = process_sources(context)
    include_dirs_list = process_includes(context)

    # Create CMakeLists file content
    cmake_file_content = cmake_file_template.format(
            module_dir=resources_dir,
            project_name=build_info['project_name'],
            cpp_flags=build_info['cpp_flags'],
            dependencies=dependencies_includes,
            include_dirs=include_dirs_list,
            sources=source_files_list,
            executables=executables_definitions,
            libraries=libraries_definitions
        )

    # Make sure the 'build' folder exists
    if not os.path.exists(build_folder):
        os.makedirs(build_folder)

    # Write CMakeLists.txt file with generated content
    cmake_file = open(cmake_lists_file_path, 'w')
    cmake_file.write(cmake_file_content)
    cmake_file.close()
#############################################################################



#############################################################################
def run_cmake():
    command = 'cd ' + build_folder_relative_path + '; cmake .'
    return subprocess.call(command, shell=True)

def run_make():
    command = 'make -C ' + build_folder_relative_path
    return subprocess.call(command, shell=True)

def main():
    init_templates()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'build':
            process(os.path.abspath('.'))
            return_code_cmake = run_cmake()
            return_code_make = run_make()
    else:
        print "Watchoowameedo?"
#############################################################################



if __name__ == '__main__':
    main()
