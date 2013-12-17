
import os
import json
import glob
import copy
import time
import sys

from urlparse import urlparse
from os.path import join as pjoin
from config import crabsys_config
from utils import *
from templates import *

build_folder_relative_path = pjoin('build', '.build')
targets_relative_path = 'build'
libraries_folder_relative_path = 'libs'

resources_dir = pjoin(os.path.dirname(os.path.realpath(__file__)), 'resources')
templates_dir = pjoin(resources_dir, 'templates')

cmake_file_template = None

build_types = {
    "crab": "crabsys"
}

def getCMakeListsFileTemplate():
    global cmake_file_template
    if cmake_file_template is None:
        cmake_file_template = get_file_content(pjoin(templates_dir, "CMakeLists.txt"))

    return cmake_file_template



#############################################################################
## Dependencies ##
##################
def process_cmake_dependency(dependency_info, context):
    if 'name' not in dependency_info:
        dependency_info['name'] = dependency_info['cmake']

    if 'search_path' in dependency_info:
        dependency_info["search_path"] = pjoin(context.current_dir, dependency_info["search_path"])

    dependency_info["path"] = pjoin(context.libs_dir, "cmake_dep_"+dependency_info['name'])
    mkdir_p(dependency_info["path"])

    return process_path_dependency(dependency_info, context)

def process_repository_dependency(dependency_info, context):
    repo_url = dependency_info['repository']
    repo_name = extract_repository_name_from_url(repo_url)

    libs_dir = os.path.abspath(pjoin(context.current_dir,
                                     context.libraries_folder_relative_path))

    dependency_absolute_path = pjoin(libs_dir, repo_name)

    if os.path.exists(dependency_absolute_path):
        if os.path.isdir(dependency_absolute_path):
            git_status(directory=dependency_absolute_path)
            if crabsys_config["update_dependencies"]:
                git_pull(directory=dependency_absolute_path)

            return process_path_dependency({
                "path": pjoin(context.libraries_folder_relative_path, repo_name),
                "name": dependency_info['name']
            }, context)
        else:
            raise Exception('Repository dependency path exists but is not' +\
                            ' a directory: ' + dependency_absolute_path)
    else:
        mkdir_p(os.path.abspath(libs_dir))

        git_clone(repo_url, directory=libs_dir)

        if 'branch' in dependency_info:
            git_checkout(dependency_info['branch'], directory=dependency_absolute_path)
        elif 'commit' in dependency_info:
            git_checkout(dependency_info['commit'], directory=dependency_absolute_path)

        return process_path_dependency({
            "path": pjoin(context.libraries_folder_relative_path, repo_name),
            "name": dependency_info['name']
        }, context)

def process_archive_dependency(dependency_info, context):
    archive_url = dependency_info['archive']

    file_name = os.path.basename(urlparse(archive_url).path)
    if 'archive_file_name' in dependency_info:
        file_name = dependency_info['archive_file_name']

    archive_file_path = pjoin(context.libs_dir, file_name)
    extracted_dir = pjoin(context.libs_dir, archive_file_path+"_extracted")

    if not os.path.isfile(archive_file_path):
        mkdir_p(context.libs_dir)
        urllib.urlretrieve (archive_url, archive_file_path)

        if not os.path.isdir(extracted_dir):
            archive = tarfile.open(archive_file_path)
            archive.extractall(path=extracted_dir, members=safemembers(archive))

    dependency_info["path"] = pjoin(extracted_dir, dependency_info['archive_path'])

    return process_path_dependency(dependency_info, context)

def process_path_dependency(dependency_info, context):
    if os.path.isabs(dependency_info['path']):
        dependency_absolute_path = dependency_info['path']
    else:
        dependency_absolute_path = os.path.abspath(
            pjoin(context.current_dir, dependency_info['path'])
        )

    dependency_build_folder_path = pjoin(dependency_absolute_path,
        context.build_folder_relative_path)

    Context(dependency_info, dependency_absolute_path, context).process(build=False)

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
    elif 'archive' in dependency_info:
        return process_archive_dependency(dependency_info, context)

    return ''

def process_dependencies(target_info, context, attribute_name='dependencies'):
    dependencies_includes = ''

    if attribute_name in target_info:
        for dependency in target_info[attribute_name]:
            definition = process_dependency(dependency, context)
            dependencies_includes = definition + dependencies_includes

    return dependencies_includes

def process_target_dynamic_lib_dependecies(target_info, context):
    dynamic_libs_post_processing = ''

    if 'dependencies_dynamic_libs_destination_path' in target_info:
        libs_path = target_info['dependencies_dynamic_libs_destination_path']

        if os.path.isabs(libs_path):
            libs_dest_path = libs_path
            libs_id_path = libs_path
        else:
            libs_dest_path = pjoin(context.current_dir,
                                     context.targets_relative_path,
                                     libs_path)
            libs_id_path = pjoin('@rpath', libs_path)

        for dynamic_lib in context.getDynamicLibsRecursively():
            dynamic_libs_post_processing +=\
                dependencies_post_processing_template.format(
                    target = target_info['name'],
                    lib_id = pjoin(libs_id_path, os.path.basename(dynamic_lib)),
                    lib_original_path = dynamic_lib,
                    lib_destination_path = pjoin(libs_dest_path, os.path.basename(dynamic_lib)),
                    libs_path=libs_dest_path
                )

    return dynamic_libs_post_processing
#############################################################################



def process_list_of_commands(info, attribute_name, current_dir):
    if attribute_name in info:
        for step in info[attribute_name]:
            if "command" in step:
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
            elif "commands" in step:
                targets_modification_time = 0
                dependencies_modification_time = 1

                if "targets" in step:
                    for path in step["targets"]:
                        full_path = pjoin(current_dir, path)

                        if os.path.isfile(full_path):
                            modification_time = os.stat( full_path ).st_mtime
                            if modification_time < targets_modification_time or targets_modification_time == 0:
                                targets_modification_time = modification_time
                        else:
                            targets_modification_time = 0
                            break

                if "dependencies" in step:
                    for path in step["dependencies"]:
                        modification_time = os.stat( pjoin(current_dir, path) ).st_mtime
                        if modification_time > dependencies_modification_time or dependencies_modification_time == 1:
                            dependencies_modification_time = modification_time

                if dependencies_modification_time > targets_modification_time:
                    process_list_of_commands(step, "commands", current_dir)



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

    process_list_of_commands(target_info, "pre-build-steps", context.current_dir)

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

def process_targets_post_build_steps(context):
    targets_definitions = ''
    if 'targets' in context.build_info:
        for target in context.build_info['targets']:
            process_list_of_commands(target, "post-build-steps", context.current_dir)
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






class GlobalContext:
    def __init__(self):
        self.projects = {}

    def add_project(self, project_name, context):
        if project_name in self.projects:
            return self.projects[project_name].current_dir == context.current_dir
        else:
            self.projects[project_name] = context
            return False


class ContextTarget:
    def __init__(self, target_info):
        pass


class Context:
    def __init__(self, build_info, current_dir, parent_context):
        self.current_dir = current_dir
        self.parent_context = parent_context
        self.libs_dir = pjoin(current_dir, libraries_folder_relative_path)
        self.build_folder = pjoin(current_dir, build_folder_relative_path)

        self.build_folder_relative_path = build_folder_relative_path
        self.targets_relative_path = targets_relative_path
        self.libraries_folder_relative_path = libraries_folder_relative_path

        self.cmake_lists_file_path = pjoin(self.build_folder, 'CMakeLists.txt')

        self.current_target = None
        self.dynamic_libs = []

        self.level = 0
        if self.parent_context:
            self.level = parent_context.level+1

        self.build_info = build_info
        if self.build_info is None:
            self.build_info = {}

        if "type" in self.build_info:
            self.build_type = build_info["type"]

            if self.build_type in build_types:
                self.build_type = build_type[self.build_type]
        elif "cmake" in self.build_info:
            self.build_type = "cmake"
        else:
            self.build_type = "crabsys"

        if self.build_type == "crabsys":
            self.processCrabFile(build_info)

        if 'project_name' not in self.build_info:
            if self.build_type == "crabsys":
                print current_dir + ': project name not defined, using folder name'
            self.build_info['project_name'] =\
                os.path.basename(os.path.dirname(current_dir+os.sep))

        self.project_name = self.build_info['project_name']

        if parent_context is not None:
            self.global_context = parent_context.global_context
        else:
            self.global_context = GlobalContext()

        self.already_processed = self.global_context.add_project(self.project_name, self)

        self.children = []
        if self.parent_context:
            self.parent_context.addChildContext(self)

    def process(self, build=False):
        if not self.already_processed:
            start_time = time.time()

            print ("--"*self.level) + "-> Processing # %s #" % (self.build_info["project_name"])

            if self.build_type == "custom":
                self.process_custom_build(build)
            elif self.build_type == "cmake":
                self.process_cmake_build(build)
            elif self.build_type == "autoconf":
                self.process_autoconf_build(build)
            elif self.build_type == "crabsys":
                print "crabsys build %d" % build
                self.process_crabsys_build(build)
            else:
                print "Unknown build type: %s\nSkipping %s..." % (self.build_type, self.project_name)

            self.already_processed = True

            print ("--"*self.level) + "-> Done - %f seconds" % (time.time()-start_time)


    def process_custom_build(self, build=False):
        current_dir = self.current_dir
        build_info = self.build_info

        if "target_files" in build_info:
            should_build = False
            for target_file in build_info["target_files"]:
                target_file_path = pjoin(current_dir, target_file)

                if os.path.isfile(target_file_path):
                    file_last_modification = os.stat(target_file_path).st_mtime
                    crab_file_last_modification = os.stat(self.getOriginalCrabFilePath()).st_mtime

                    if crab_file_last_modification > file_last_modification:
                        should_build = True
                else:
                    should_build = True

            if not should_build:
                return
        else:
            build_info["target_files"] = []

        if "includes" not in build_info:
            build_info["includes"] = []

        self.current_target = self.build_info
        dependencies = process_dependencies(self.build_info, self)
        process_dependencies(self.build_info, self, attribute_name="build_dependencies")

        process_list_of_commands(build_info, "pre-build-steps", current_dir)
        process_list_of_commands(build_info, "build-steps", current_dir)
        process_list_of_commands(build_info, "post-build-steps", current_dir)

        for target_file in build_info["target_files"]:
            if is_dynamic_lib(target_file):
                self.addDynamicLib(target_file)

            os.utime(pjoin(current_dir, target_file), None)
            

        target = custom_dependency_template.format(
            name=self.build_info['name'],
            includes=add_path_prefix_and_join(build_info["includes"], current_dir, ' '),
            libs=add_path_prefix_and_join(build_info["target_files"], current_dir, ' '))

        self.generateCMakeListsFile(dependencies+'\n'+target, "")

        if build:
            processed_targets = run_cmake(self.build_folder)


    def process_autoconf_build(self, build=False):
        build_info = self.build_info

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

        self.process_custom_build(build)


    def process_cmake_build(self, build=False):
        self.current_target = self.build_info
        dependencies = process_dependencies(self.build_info, self)
        process_dependencies(self.build_info, self, attribute_name="build_dependencies")

        search_path_include = ''
        if 'search_path' in self.build_info:
            search_path = pjoin(self.current_dir,
                                self.build_info['search_path'])
            search_path_include = cmake_dependency_search_path_template.format(
                    search_path=search_path
                )

        name = self.build_info['name']

        target = '\n'.join([dependencies, search_path_include,
            cmake_dependency_template.format(name=name, upper_name=name.upper())])

        self.generateCMakeListsFile(target, "")

        if build:
            processed_targets = run_cmake(self.build_folder)

        process_list_of_commands(self.build_info, "pre-build-steps", self.current_dir)
        process_list_of_commands(self.build_info, "post-build-steps", self.current_dir)


    def process_crabsys_build(self, build=False):
        sources_lists = process_sources_lists(self)

        targets = process_targets(self)

        self.generateCMakeListsFile(targets, sources_lists)

        if build:
            processed_targets = run_cmake(self.build_folder)

            for target in processed_targets:
                if is_dynamic_lib(processed_targets[target]["location"]):
                    self.addDynamicLib(lib)

            run_make(self.build_folder)

            process_targets_post_build_steps(self)



    def processCrabFile(self, build_info):
        self.crab_file_path = pjoin(self.current_dir, 'crab.json')

        try:
            cmake_file_last_modification = os.stat(self.cmake_lists_file_path).st_mtime
            crab_file_last_modification = os.stat(self.crab_file_path).st_mtime

            #if crab_file_last_modification < cmake_file_last_modification:
            #    return
        except OSError, e:
            pass

        if self.crab_file_path:
            if os.path.isfile(self.crab_file_path):
                # Read crab file and parse as json
                self.build_info = json.loads(get_file_content(self.crab_file_path))
            else:
                print "crab.json file not found - setting to default build"
                self.build_info = copy.deepcopy(crabsys_config["default_build"])
        else:
            self.build_info = build_info

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


    def generateCMakeListsFile(self, targets, sources_lists):
        # Create CMakeLists file content
        cmake_file_content = getCMakeListsFileTemplate().format(
                module_dir=resources_dir,
                project_name=self.project_name,
                targets=targets,
                sources_lists=sources_lists
            )

        if os.path.isfile(self.cmake_lists_file_path):
            if get_file_content(self.cmake_lists_file_path) == cmake_file_content:
                return
            if os.stat(self.cmake_lists_file_path).st_mtime > os.stat(self.getOriginalCrabFilePath()).st_mtime:
                return

        # Make sure the 'build' folder exists
        if not os.path.exists(self.build_folder):
            os.makedirs(self.build_folder)

        # Write CMakeLists.txt file with generated content
        cmake_file = open(self.cmake_lists_file_path, 'w')
        cmake_file.write(cmake_file_content)
        cmake_file.close()

    def getOriginalCrabFilePath(self):
        if self.build_type == "crabsys" and os.path.isfile(self.crab_file_path):
            return os.path.abspath(self.crab_file_path)
        elif self.parent_context:
            return self.parent_context.getOriginalCrabFilePath()
        else:
            print "Warning: No crab file found! This shouldn't happen!"
            return None
