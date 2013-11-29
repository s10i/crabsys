#!/usr/bin/env python

import os
import os.path
import errno
import sys
import subprocess
import multiprocessing
import re

from os.path import join as pjoin
from context import Context, GlobalContext, build_folder_relative_path, targets_relative_path
from utils import *
from templates import *
from dependencies import process_dependencies, process_target_dynamic_lib_dependecies

resources_dir = pjoin(os.path.dirname(os.path.realpath(__file__)), 'resources')

def init_templates():
    templates_dir = pjoin(resources_dir, 'templates')

    global cmake_file_template
    cmake_file_template = get_file_content(pjoin(templates_dir, "CMakeLists.txt"))


#############################################################################
## Executables ##
#################
def process_executable(target_info, context):
    linux_rpath = ""
    if "dependencies_dynamic_libs_destination_path" in target_info:
        linux_rpath = pjoin("$ORIGIN",
            target_info["dependencies_dynamic_libs_destination_path"])

    return executable_template.format(
        name=target_info['name'],
        target_path=pjoin(context.current_dir, targets_relative_path),
        cmake_libraries=context.cmake_libraries[target_info['name']],
        compile_flags=target_info['compile_flags']+target_info['flags'],
        link_flags=target_info['link_flags']+' '+target_info['flags'],
        sources_lists=context.sources_lists,
        linux_rpath=linux_rpath
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

    target += process_target_dynamic_lib_dependecies(target_info, context)

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
    context = Context(current_dir, None, parent_context, process)

    if "build-steps" in build_info:
        for step in build_info["build-steps"]:
            command = [ step["command"] ]
            if "params" in step:
                command += step["params"]

            directory = current_dir
            if "directory" in step:
                directory = pjoin(current_dir, step["directory"])

            system_command(command, directory)

    if "lib_files" in build_info:
        for lib in build_info["lib_files"]:
            lib_extension = os.path.splitext(lib)[1]
            if re.match("^(.*)\.dylib", lib) or re.match("^(.*)\.so(\.[0-9]*)?", lib):
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

    context = Context(current_dir, crab_file_path, parent_context, process)

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
