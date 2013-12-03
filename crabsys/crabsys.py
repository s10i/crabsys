#!/usr/bin/env python

import os
import os.path
import sys
import subprocess
import multiprocessing
import glob
import argparse

from os.path import join as pjoin
from context import Context, GlobalContext, build_folder_relative_path, targets_relative_path
from utils import *
from templates import *
from dependencies import process_dependencies, process_target_dynamic_lib_dependecies
from config import loadConfiguration


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

platform_names = {
    "linux": "linux2",
    "linux2": "linux2",
}

def process_system_specific(target_info, context):
    if 'system_specific' in target_info:
        for system in target_info['system_specific']:
            platform = system
            if system in platform_names:
                platform = platform_names[system]

            if platform == sys.platform:
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
    process_dependencies(target_info, context, attribute_name="build_dependencies")

    sources = process_target_sources(target_info, context)
    context.sources_lists = process_target_sources_lists(target_info, context)
    includes = process_target_includes(target_info, context)
    target = ''

    if sources != '' or context.sources_lists != '':
        if target_info['type'] == 'executable':
            target = process_executable(target_info, context)
        elif target_info['type'] == 'library':
            target = process_library(target_info, context)
    else:
        target = custom_target_template.format(name=target_info['name'])

    target += process_target_dynamic_lib_dependecies(target_info, context)

    return '\n'.join([dependencies, includes, sources, target])

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
    sources_list = ''

    for source in sources:
        if type(source)==type({}):
            if 'glob' in source:
                glob_sources = glob.glob(pjoin(context.current_dir, source['glob']))
                if len(glob_sources) > 0:
                    sources_list += '\n'.join(glob_sources)+'\n'
        else:
            sources_list += pjoin(context.current_dir, source)+'\n'

    return sources_list

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
    if 'sources' not in target_info or len(target_info['sources']) == 0:
        return ''

    processed_sources = process_sources(target_info['sources'], context)

    if len(processed_sources) == 0:
        return ''

    return sources_template.format(
            name = target_info['name'],
            sources = processed_sources
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
    )

def process_target_includes(target_info, context):
    include_variable = ''
    if 'includes' in target_info:
        include_variable = target_includes_variable_template.format(
                name = target_info['name'],
                sources = process_includes(target_info['includes'], context)
            )

    return include_variable
#############################################################################



#############################################################################
def process(current_dir, build_info=None, parent_context=None):
    context = Context(build_info, current_dir, parent_context, process)

    if context.already_processed:
        return

    if context.build_type == "custom":
        process_custom_build(context)
    elif context.build_type == "cmake":
        process_cmake_build(context)
    elif context.build_type == "autoconf":
        process_autoconf_build(context)
    elif context.build_type == "crabsys":
        process_crabsys_build(context)
    else:
        print "Unknown build type: %s\nSkipping %s..." % (context.build_type, context.project_name)


def process_custom_build(context):
    current_dir = context.current_dir
    build_info = context.build_info

    if "target_files" not in build_info:
        build_info["target_files"] = []

    should_build = False
    for target_file in build_info["target_files"]:
        file_last_modification = os.stat(pjoin(current_dir, target_file)).st_mtime
        crab_file_last_modification = os.stat(context.getOriginalCrabFilePath()).st_mtime

        if crab_file_last_modification > file_last_modification:
            should_build = True

    if not should_build:
        return

    context.current_target = context.build_info
    dependencies = process_dependencies(context.build_info, context)
    process_dependencies(context.build_info, context, attribute_name="build_dependencies")

    if "build-steps" in build_info:
        for step in build_info["build-steps"]:
            command = [ step["command"] ]
            if "params" in step:
                command += step["params"]

            directory = current_dir
            if "directory" in step:
                directory = pjoin(current_dir, step["directory"])

            (retcode, stdout, stderr) = system_command(command, directory)
            if retcode != 0:
                print "Command returned non-zero code: %s" % (step["command"])
                print stderr

    for lib in build_info["target_files"]:
        if is_dynamic_lib(lib):
            context.addDynamicLib(lib)
        

    target = custom_dependency_template.format(
        name=context.build_info['name'],
        includes=add_path_prefix_and_join(build_info["includes"], current_dir, ' '),
        libs=add_path_prefix_and_join(build_info["target_files"], current_dir, ' '))

    context.generateCMakeListsFile(dependencies+'\n'+target, "")
    processed_targets = run_cmake(context.build_folder)


def process_autoconf_build(context):
    build_info = context.build_info

    build_info["build-steps"] = [
        { "command": "./configure" },
        { "command": "make" }
    ]

    configure_command = build_info["build-steps"][0]
    make_command = build_info["build-steps"][1]

    # Run directory
    if "autoconf_directory" in build_info:
        configure_command["directory"] = build_info["autoconf_directory"]
        make_command["directory"] = build_info["autoconf_directory"]

    if "configure_directory" in build_info:
        configure_command["directory"] = build_info["configure_directory"]

    if "make_directory" in build_info:
        make_command["directory"] = build_info["make_directory"]

    # Commands parameters
    if "configure_params" in build_info:
        configure_command["params"] = build_info["configure_params"]

    if "make_params" in build_info:
        make_command["params"] = build_info["make_params"]

    process_custom_build(context)


def process_cmake_build(context):
    context.current_target = context.build_info
    dependencies = process_dependencies(context.build_info, context)
    process_dependencies(context.build_info, context, attribute_name="build_dependencies")

    search_path_include = ''
    if 'search_path' in context.build_info:
        search_path = pjoin(context.current_dir,
                            context.build_info['search_path'])
        search_path_include = cmake_dependency_search_path_template.format(
                search_path=search_path
            )

    name = context.build_info['name']

    target = '\n'.join([dependencies, search_path_include,
        cmake_dependency_template.format(name=name, upper_name=name.upper())])

    context.generateCMakeListsFile(target, "")
    processed_targets = run_cmake(context.build_folder)


def process_crabsys_build(context):
    sources_lists = process_sources_lists(context)
    targets = process_targets(context)

    context.generateCMakeListsFile(targets, sources_lists)

    processed_targets = run_cmake(context.build_folder)

    for target in processed_targets:
        if is_dynamic_lib(processed_targets[target]["location"]):
            context.addDynamicLib(lib)
#############################################################################



#############################################################################
def run_cmake(directory=None):
    (retcode, stdout, stderr) = system_command(['cmake', '.'], directory)

    if retcode != 0:
        print stderr
        return None

    current_project_name = None
    targets = {}
    for line in stderr.split('\n'):
        if line.startswith(cmake_output_variables['name']):
            current_project_name = line[len(cmake_output_variables['name']):]
            targets[current_project_name] = {}
        elif line.startswith(cmake_output_variables['location']):
            current_project_location = line[len(cmake_output_variables['location']):]
            targets[current_project_name]['location'] = current_project_location

    return targets

def run_make(directory=None, parallel_build=True):
    cpu_count = multiprocessing.cpu_count()
    if not parallel_build:
        cpu_count = 1

    (retcode, stdout, stderr) = system_command( ['make', '-j' + str(cpu_count)], pjoin(directory, build_folder_relative_path) )

    if retcode != 0:
        print "Error running make at directory: %s" % (directory)
        print stderr

    return retcode

def parseArguments():
    parser = argparse.ArgumentParser(description='C/C++ Recursive Automated Build System')
    parser.add_argument('--update-dependencies', action='store_true', dest='update_dependencies', default=None,
                        help='Update all repository dependencies before building')
    parser.add_argument('--dont-update-dependencies', action='store_false', dest='update_dependencies', default=None,
                        help='DO NOT update any repository dependencies before building')
    parser.add_argument('--config', metavar='CONFIG', action='store', dest='config_file_path',
                        help='Configuration file path')
    parser.add_argument('--path', metavar='PATH', action='store', dest='path', default='.',
                        help='Path of where the processing should start')
    parser.add_argument('action', default='build', nargs='?',
                        help='Crabsys action (only build is supported for now)')

    args = parser.parse_args()

    #print args

    return args

def main():
    args = parseArguments()

    args_config = {}
    if args.update_dependencies:
        args_config["update_dependencies"] = args.update_dependencies

    loadConfiguration(args.config_file_path, args_config)

    if args.action == 'build':
        process(os.path.abspath(args.path))
        run_make(os.path.abspath(args.path))
    else:
        print "Action not supported: %s" % (args.action)
#############################################################################



if __name__ == '__main__':
    main()
