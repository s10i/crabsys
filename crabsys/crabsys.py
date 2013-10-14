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
        self.cmake_libraries = {}
        self.cmake_includes = {}
        self.current_target = None

    def init_cmake_dependencies(self, target_info):
        target_name = target_info['name']

        self.cmake_libraries[target_name] = ''
        self.cmake_includes[target_name] = ''

    def append_cmake_dependency(self, target_info, includes, libraries):
        target_name = target_info['name']

        self.cmake_libraries[target_name] += ' ' + libraries
        self.cmake_includes[target_name] += ' ' + includes



def get_file_content(file_path):
    file_handle = open(file_path, 'r')
    content = file_handle.read()
    file_handle.close()
    return content




#############################################################################
## Templates ##
###############
executable_template = ''+\
    'add_executable({name} ${{{name}_SRCS}})\n'+\
    'target_link_libraries({name} ${{{name}_LIBS_LINK_LIBS}} {cmake_libraries})\n'+\
    'set_target_properties({name} PROPERTIES RUNTIME_OUTPUT_DIRECTORY '+\
        '{target_path})\n'+\
    'set_target_properties({name} PROPERTIES COMPILE_FLAGS "{flags}")\n'

library_template = ''+\
    'add_library({name} ${{{name}_SRCS}})\n'+\
    'target_link_libraries({name} ${{{name}_LIBS_LINK_LIBS}} {cmake_libraries})\n'+\
    'set_target_properties({name} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY '+\
        '{target_path})\n'+\
    'set_target_properties({name} PROPERTIES COMPILE_FLAGS "{flags}")\n'+\
    'set({name}_LIB {name})\n'

export_template = ''+\
    'export_lib_macro({name})\n'

target_sources_template = ''+\
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

cmake_dependency_template = ''+\
    'find_package({name} REQUIRED)\n'

cmake_dependency_search_path_template = ''+\
    'set(CMAKE_MODULE_PATH ${{CMAKE_MODULE_PATH}} "{search_path}")\n'

def init_templates():
    templates_dir = resources_dir + '/templates'

    global cmake_file_template
    cmake_file_template = get_file_content(templates_dir+"/CMakeLists.txt")
#############################################################################



#############################################################################
## Dependencies ##
##################
def process_cmake_dependency(dependency_info, context):
    name = dependency_info['cmake']
    context.append_cmake_dependency(context.current_target,
                                    '${' + name.upper() + '_INCLUDE_DIR}',
                                    '${' + name.upper() + '_LIBRARIES}')

    search_path_include = ''
    if 'search_path' in dependency_info:
        search_path = context.current_dir + '/' +\
                      dependency_info['search_path']
        search_path_include = cmake_dependency_search_path_template.format(
                search_path=search_path
            )

    return search_path_include + cmake_dependency_template.format(name=name)

def process_repository_dependency(dependency_info, context):
    return repository_dependency_template.format(
        repository_url=dependency_info['repository']
    )

def process_path_dependency(dependency_info, context):
    dependency_absolute_path = os.path.abspath(context.current_dir + '/' +\
        dependency_info['path'])

    process(dependency_absolute_path, context)

    dependency_build_folder_path = dependency_absolute_path + '/' +\
        build_folder_relative_path

    return path_dependency_template.format(
        build_path=dependency_build_folder_path,
        prefix=context.current_target['name'],
        name=dependency_info['name']
    )

def process_dependency(dependency_info, context):
    if 'repository' in dependency_info:
        return process_repository_dependency(dependency_info, context)
    elif 'path' in dependency_info:
        return process_path_dependency(dependency_info, context)
    elif 'cmake' in dependency_info:
        return process_cmake_dependency(dependency_info, context)

    return ''

def process_dependencies(target_info, context):
    dependencies_includes = ''
    context.init_cmake_dependencies(target_info)

    if 'dependencies' in target_info:
        for dependency in target_info['dependencies']:
            dependencies_includes += process_dependency(dependency, context)

    return dependencies_includes
#############################################################################



#############################################################################
## Executables ##
#################
def process_executable(target_info, context):
    return executable_template.format(
        name=target_info['name'],
        target_path=context.current_dir+'/'+targets_relative_path,
        project_name=context.build_info['project_name'],
        cmake_libraries=context.cmake_libraries[target_info['name']],
        flags=target_info['flags']
    )
#############################################################################



#############################################################################
## Libraries ##
###############
def process_library(target_info, context):
    return library_template.format(
        name=target_info['name'],
        target_path=context.current_dir+'/'+targets_relative_path,
        project_name=context.build_info['project_name'],
        cmake_libraries=context.cmake_libraries[target_info['name']],
        flags=target_info['flags']
    )
#############################################################################



#############################################################################
## Targets ##
#############
def process_target(target_info, context):
    context.current_target = target_info
    if 'flags' not in target_info:
        target_info['flags'] = ''

    dependencies = process_dependencies(target_info, context)
    sources = process_target_sources(target_info, context)
    includes = process_target_includes(target_info, context)
    target = ''
    export = export_template.format(name=target_info['name'])

    if sources != '':
        if target_info['type'] == 'executable':
            target = process_executable(target_info, context)
        elif target_info['type'] == 'library':
            target = process_library(target_info, context)

    return '\n'.join([dependencies, includes, sources, target, export])

def process_targets(context):
    targets_definitions = ''
    if 'targets' in context.build_info:
        for target in context.build_info['targets']:
            targets_definitions += process_target(target, context)
    return targets_definitions
#############################################################################



#############################################################################
## Sources ##
#############
def process_sources(sources, context):
    return '\n'.join(
        [context.current_dir+"/"+source
         for source in sources]
    )

def process_target_sources(target_info, context):
    if 'sources' not in target_info:
        return ''

    return target_sources_template.format(
            name = target_info['name'],
            sources = process_sources(target_info['sources'], context)
        )
#############################################################################



#############################################################################
## Includes ##
#############
def process_includes(includes, context):
    current_target_name = context.current_target['name']

    return '\n'.join(
        [context.current_dir+"/"+include_dir
         for include_dir in includes]
    ) + context.cmake_includes[current_target_name]

def process_target_includes(target_info, context):
    include_variable = ''
    if 'includes' in target_info:
        include_variable = target_includes_variable_template.format(
                name = target_info['name'],
                sources = process_includes(target_info['includes'], context)
            )

    return include_variable + target_includes_template.format(
            name = target_info['name']
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

        #if crab_file_last_modification < cmake_file_last_modification:
        #    return
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

    targets = process_targets(context)

    # Create CMakeLists file content
    cmake_file_content = cmake_file_template.format(
            module_dir=resources_dir,
            project_name=build_info['project_name'],
            targets=targets
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
