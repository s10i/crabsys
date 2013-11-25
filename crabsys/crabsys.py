#!/usr/bin/env python

import json
import os
import os.path
import errno
import sys
import subprocess
import multiprocessing

from os.path import join as pjoin

resources_dir = pjoin(os.path.dirname(os.path.realpath(__file__)), 'resources')
build_folder_relative_path = pjoin('build', '.build')
targets_relative_path = 'build'
libraries_folder_relative_path = 'libs'


class GlobalContext:
    def __init__(self):
        self.projects = {}

    def add_project(self, project_name):
        if project_name in self.projects:
            return True
        else:
            self.projects[project_name] = True
            return False

class Context:
    def __init__(self, current_dir, crab_file_path, parent_context):
        self.current_dir = current_dir
        self.parent_context = parent_context
        self.cmake_libraries = {}
        self.cmake_includes = {}
        self.current_target = None
        self.crab_file_path = crab_file_path
        self.dynamic_libs = []

        if crab_file_path:
            # Read crab file and parse as json
            self.build_info = json.loads(get_file_content(crab_file_path))
        else:
            self.build_info = {}

        if 'project_name' not in self.build_info:
            print current_dir + ': project name not defined, using folder name'
            self.build_info['project_name'] =\
                os.path.basename(os.path.dirname(current_dir))

        self.project_name = self.build_info['project_name']

        if parent_context is not None:
            self.global_context = parent_context.global_context
        else:
            self.global_context = GlobalContext()

        self.already_processed = self.global_context.add_project(self.project_name)

        self.children = []
        if parent_context:
            parent_context.addChildContext(self)

    def init_cmake_dependencies(self, target_info):
        target_name = target_info['name']

        self.cmake_libraries[target_name] = ''
        self.cmake_includes[target_name] = ''

    def append_cmake_dependency(self, target_info, includes, libraries):
        target_name = target_info['name']

        self.cmake_libraries[target_name] += ' ' + libraries
        self.cmake_includes[target_name] += ' ' + includes

    def addChildContext(self, context):
        self.children.append(context)

    def addDynamicLib(self, lib):
        self.dynamic_libs.append(lib)

    def getDynamicLibsRecursively(self):
        dynamic_libs_deps = []
        for child in self.children:
            dynamic_libs_deps += [pjoin(child.current_dir, lib) for lib in child.dynamic_libs]
            dynamic_libs_deps += child.getDynamicLibsRecursively()

        return dynamic_libs_deps


def get_file_content(file_path):
    file_handle = open(file_path, 'r')
    content = file_handle.read()
    file_handle.close()
    return content

def extract_repository_name_from_url(repo_url):
    last_slash_index = repo_url.rfind('/')
    repo_name = repo_url[last_slash_index+1:]

    if repo_name[-4:] == '.git':
        repo_name = repo_name[:-4]

    return repo_name

def add_path_prefix_and_join(values, prefix, separator):
    return separator.join([pjoin(prefix, value) for value in values])

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def system_command(params=None, directory=None):
    original_working_directory = os.getcwd()

    os.chdir(directory)
    return_code = subprocess.call(params, shell=False)

    os.chdir(original_working_directory)

    return return_code

def git_command(params=None, directory=None):
    return system_command(['git'] + params, directory)

def git_clone(url, directory=None):
    if git_command(params=['clone', url], directory=directory) != 0:
        raise Exception('Error cloning repository: ' + url)

def git_status(directory=None):
    if git_command(params=['status'], directory=directory) != 0:
        raise Exception('Error getting repository status: ' + directory)

def git_pull(directory=None):
    if git_command(params=['pull'], directory=directory) != 0:
        raise Exception('Error running git pull: ' + directory)

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
    'find_package({name} REQUIRED)\n'

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

def init_templates():
    templates_dir = pjoin(resources_dir, 'templates')

    global cmake_file_template
    cmake_file_template = get_file_content(pjoin(templates_dir, "CMakeLists.txt"))
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
        search_path = pjoin(context.current_dir,
                            dependency_info['search_path'])
        search_path_include = cmake_dependency_search_path_template.format(
                search_path=search_path
            )

    return search_path_include + cmake_dependency_template.format(name=name)

def process_repository_dependency(dependency_info, context):
    repo_url = dependency_info['repository']
    repo_name = extract_repository_name_from_url(repo_url)

    libs_dir = os.path.abspath(pjoin(context.current_dir,
                                     libraries_folder_relative_path))

    dependency_absolute_path = pjoin(libs_dir, repo_name)

    if os.path.exists(dependency_absolute_path):
        if os.path.isdir(dependency_absolute_path):
            git_status(directory=dependency_absolute_path)
            git_pull(directory=dependency_absolute_path)

            return process_path_dependency({
                "path": pjoin(libraries_folder_relative_path, repo_name),
                "name": dependency_info['name']
            }, context)
        else:
            raise Exception('Repository dependency path exists but is not' +\
                            ' a directory: ' + dependency_absolute_path)
    else:
        mkdir_p(os.path.abspath(libs_dir))

        git_clone(repo_url, directory=libs_dir)        

        return process_path_dependency({
            "path": pjoin(libraries_folder_relative_path, repo_name),
            "name": dependency_info['name']
        }, context)

def process_path_dependency(dependency_info, context):
    if os.path.isabs(dependency_info['path']):
        dependency_absolute_path = dependency_info['path']
    else:
        dependency_absolute_path = os.path.abspath(
            pjoin(context.current_dir, dependency_info['path'])
        )

    dependency_build_folder_path = pjoin(dependency_absolute_path,
        build_folder_relative_path)

    process(dependency_absolute_path, dependency_info, context)

    if "type" in dependency_info:
        dependency_type = dependency_info["type"]
        if dependency_type == "custom":
            return custom_dependency_template.format(
                includes=add_path_prefix_and_join(dependency_info["include_dirs"],
                                                  dependency_absolute_path,
                                                  ' '),
                libs=add_path_prefix_and_join(dependency_info["lib_files"],
                                              dependency_absolute_path,
                                              ' '),
                prefix=context.current_target['name'],
                name=dependency_info['name']
            )
        else:
            return path_dependency_template.format(
                build_path=dependency_build_folder_path,
                prefix=context.current_target['name'],
                name=dependency_info['name']
            )
    else:
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
        target_path=pjoin(context.current_dir, targets_relative_path),
        cmake_libraries=context.cmake_libraries[target_info['name']],
        compile_flags=target_info['compile_flags']+target_info['flags'],
        link_flags=target_info['link_flags']+target_info['flags'],
        sources_lists=context.sources_lists
    )
#############################################################################



#############################################################################
## Libraries ##
###############
def process_library(target_info, context):
    return library_template.format(
        name=target_info['name'],
        target_path=pjoin(context.current_dir, targets_relative_path),
        cmake_libraries=context.cmake_libraries[target_info['name']],
        compile_flags=target_info['compile_flags']+' '+target_info['flags'],
        link_flags=target_info['link_flags']+' '+target_info['flags'],
        sources_lists=context.sources_lists
    )
#############################################################################



#############################################################################
## System specific ##
#####################
def append_attribute(target, source, attribute, empty_value, prefix):
    if attribute in source:
        if attribute not in target:
            target[attribute] = empty_value
        target[attribute] += prefix + source[attribute]

def add_system_specific_info(target_info, system_info, context):
    append_attribute(target_info, system_info, 'flags', '', ' ')
    append_attribute(target_info, system_info, 'compile_flags', '', ' ')
    append_attribute(target_info, system_info, 'link_flags', '', ' ')
    append_attribute(target_info, system_info, 'sources', [], [])
    append_attribute(target_info, system_info, 'dependencies', [], [])
    append_attribute(target_info, system_info, 'includes', [], [])

def process_system_specific(target_info, context):
    if 'system_specific' in target_info:
        for system in target_info['system_specific']:
            if system == 'linux':
                system = 'linux2'

            if system == sys.platform:
                add_system_specific_info(target_info,
                    target_info['system_specific'][system],
                    context)
#############################################################################



#############################################################################
## Targets ##
#############
def process_target(target_info, context):
    context.current_target = target_info
    if 'flags' not in target_info:
        target_info['flags'] = ''
    if 'compile_flags' not in target_info:
        target_info['compile_flags'] = ''
    if 'link_flags' not in target_info:
        target_info['link_flags'] = ''

    process_system_specific(target_info, context)

    dependencies = process_dependencies(target_info, context)
    sources = process_target_sources(target_info, context)
    context.sources_lists = process_target_sources_lists(target_info, context)
    includes = process_target_includes(target_info, context)
    target = ''
    export = export_template.format(name=target_info['name'])

    if sources != '' or context.sources_lists != '':
        if target_info['type'] == 'executable':
            target = process_executable(target_info, context)
        elif target_info['type'] == 'library':
            target = process_library(target_info, context)

    if 'dependencies_dynamic_libs_destination_path' in target_info:
        libs_path = target_info['dependencies_dynamic_libs_destination_path']

        if os.path.isabs(libs_path):
            libs_dest_path = libs_path
            libs_id_path = libs_path
        else:
            libs_dest_path = pjoin(context.current_dir,
                                     targets_relative_path,
                                     libs_path)
            libs_id_path = pjoin('@rpath', libs_path)

        for dynamic_lib in context.getDynamicLibsRecursively():
            target += dependencies_post_processing_template.format(
                    target = target_info['name'],
                    lib_id = pjoin(libs_id_path, os.path.basename(dynamic_lib)),
                    lib_original_path = dynamic_lib,
                    lib_destination_path = pjoin(libs_dest_path, os.path.basename(dynamic_lib)),
                    libs_path=libs_dest_path
                )

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
        [pjoin(context.current_dir, source)
         for source in sources]
    )

def process_sources_list(sources_list, context):
    definition = ''
    if 'name' in sources_list:
        definition += sources_template.format(
            name = sources_list['name'],
            sources = process_sources(sources_list['sources'], context)
        )

    return definition + sources_template.format(
            name = "__LIST_" + str(context.sources_list_index),
            sources = process_sources(sources_list['sources'], context)
        )

def process_sources_lists(context):
    definitions = ''

    if 'sources_lists' in context.build_info:
        sources_lists = context.build_info['sources_lists']
        for index, sources_list in enumerate(sources_lists):
            context.sources_list_index = index
            definitions += process_sources_list(sources_list, context)

    return definitions

def process_target_sources(target_info, context):
    if 'sources' not in target_info:
        return ''

    return sources_template.format(
            name = target_info['name'],
            sources = process_sources(target_info['sources'], context)
        )

def process_target_sources_lists(target_info, context):
    sources_lists = ''
    if 'sources_lists' in target_info:
        for list_id in target_info['sources_lists']:
            if isinstance(list_id, basestring):
                sources_lists += ' ${' + list_id + '_SRCS}'
            elif isinstance(list_id, int):
                sources_lists += ' ${__LIST_' + str(list_id) + '_SRCS}'

    return sources_lists
#############################################################################



#############################################################################
## Includes ##
#############
def process_includes(includes, context):
    current_target_name = context.current_target['name']

    return '\n'.join(
        [pjoin(context.current_dir, include_dir)
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
def process(current_dir, build_info=None, parent_context=None):
    if build_info and "type" in build_info:
        build_type = build_info["type"]

        if build_type == "custom":
            process_custom_build(current_dir, build_info, parent_context)
        elif build_type == "crab" or build_type == "crabsys":
            process_crabsys_build(current_dir, parent_context)
    else:
        process_crabsys_build(current_dir, parent_context)


def process_custom_build(current_dir, build_info, parent_context=None):
    context = Context(current_dir, None, parent_context)

    if "build-steps" in build_info:
        for step in build_info["build-steps"]:
            command = [ step["command"] ]
            if "params" in step:
                command += step["params"]
            system_command(command, current_dir)

    if "lib_files" in build_info:
        for lib in build_info["lib_files"]:
            lib_extension = os.path.splitext(lib)[1]
            if lib_extension == ".dylib" or lib_extension == ".so":
                context.addDynamicLib(lib)



def process_crabsys_build(current_dir, parent_context=None):
    build_folder = pjoin(current_dir, build_folder_relative_path)
    cmake_lists_file_path = pjoin(build_folder, 'CMakeLists.txt')
    crab_file_path = pjoin(current_dir, 'crab.json')

    try:
        cmake_file_last_modification = os.stat(cmake_lists_file_path).st_mtime
        crab_file_last_modification = os.stat(crab_file_path).st_mtime

        #if crab_file_last_modification < cmake_file_last_modification:
        #    return
    except OSError, e:
        pass

    context = Context(current_dir, crab_file_path, parent_context)

    if context.already_processed:
        return

    sources_lists = process_sources_lists(context)
    targets = process_targets(context)

    # Create CMakeLists file content
    cmake_file_content = cmake_file_template.format(
            module_dir=resources_dir,
            project_name=context.project_name,
            targets=targets,
            sources_lists=sources_lists
        )

    # Make sure the 'build' folder exists
    if not os.path.exists(build_folder):
        os.makedirs(build_folder)

    # Write CMakeLists.txt file with generated content
    cmake_file = open(cmake_lists_file_path, 'w')
    cmake_file.write(cmake_file_content)
    cmake_file.close()

    run_cmake(build_folder)
#############################################################################



#############################################################################
def run_cmake(directory=None):
    cmake_process = subprocess.Popen(['cmake', '.'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     cwd=directory,
                                     shell=False)

    stdout, stderr = cmake_process.communicate()

    retcode = cmake_process.poll()

    current_project_name = None
    targets = {}
    for line in stderr.split('\n'):
        if line.startswith(cmake_output_variables['name']):
            current_project_name = line[len(cmake_output_variables['name']):]
            targets[current_project_name] = {}
        elif line.startswith(cmake_output_variables['location']):
            current_project_location = line[len(cmake_output_variables['location']):]
            targets[current_project_name]['location'] = current_project_location

    #print targets

    return retcode

def run_make():
    cpu_count = multiprocessing.cpu_count()
    command = 'make -C ' + build_folder_relative_path + ' -j' + str(cpu_count)
    return subprocess.call(command, shell=True)

def main():
    init_templates()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'build':
            process(os.path.abspath('.'))
            return_code_make = run_make()
    else:
        print "Watchoowameedo?"
#############################################################################



if __name__ == '__main__':
    main()
