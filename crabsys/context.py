
import os
import json
import copy
import time
import sys

from os.path import join as pjoin
from config import crabsys_config
from utils import *

import pystache

build_folder_relative_path = pjoin('build', '.build')
targets_relative_path = 'build'
libraries_folder_relative_path = 'libs'

resources_dir = pjoin(os.path.dirname(os.path.realpath(__file__)), 'resources')
templates_dir = pjoin(resources_dir, 'templates')

build_types = {
    "crab": "crabsys"
}

cmake_build_cmake_lists_template = get_file_content(pjoin(templates_dir, "CMakeBuild_CMakeLists.txt"))
crabsys_build_cmake_lists_template = get_file_content(pjoin(templates_dir, "CrabsysBuild_CMakeLists.txt"))

platform_names = {
    "linux": "linux2",
    "linux2": "linux2",
}


class GlobalContext:
    def __init__(self):
        self.projects = {}

    def add_project(self, project_name, context):
        if project_name in self.projects:
            return self.projects[project_name].current_dir == context.current_dir
        else:
            self.projects[project_name] = context
            return False

class BuildStep:
    def __init__(self, build_step_info, context):
        self.context = context

        self.directory = ""
        if "directory" in build_step_info:
            self.directory = build_step_info["directory"]

        self.params = []
        if "params" in build_step_info:
            self.params = build_step_info["params"]

        if "command" not in build_step_info:
            raise Exception("A command requires a 'command' attribute!")
        self.command = build_step_info["command"]

    def run(self):
        (retcode, stdout, stderr) = system_command([self.command]+self.params, pjoin(self.context.current_dir, self.directory))
        if retcode != 0:
            print stderr
            raise Exception("Command returned non-zero code: %s" % (self.command))


def parseListOfBuildSteps(build_steps_info, context, attribute=None):
    if attribute:
        if attribute in build_steps_info:
            build_steps_info = build_steps_info[attribute]
        else:
            return []

    return [BuildStep(info, context) for info in build_steps_info]


class Target:
    def __init__(self, target_info, context):
        self.context = context

        start_time = time.time()
        #print ("--"*self.context.level) + "-> Processing # %s #" % (self.name)
        print ("--"*self.context.level) + "-> Processing # %s #" % ("")

        self.processed = False

        self.name = None
        self.type = None
        self.parallel_build = True

        self.sources_lists = []
        self.includes = []
        self.target_files = []
        self.sources = []

        self.build_steps = []
        self.pre_build_steps = []
        self.post_build_steps = []

        self.flags = []
        self.compile_flags = []
        self.link_flags = []

        self.cmake_search_path = ""
        self.build_type = "crabsys"
        self.built = False

        self.dependencies = []
        self.build_dependencies = []

        self.linux_rpath = ""
        self.dynamic_libs_destination_path = ""

        self.extend(target_info)

        if 'system_specific' in target_info:
            for system in target_info['system_specific']:
                platform = system
                if system in platform_names:
                    platform = platform_names[system]

                if platform == sys.platform:
                    self.extend(target_info['system_specific'][system])

        self.process()
        self.build()

        print ("--"*self.context.level) + "-> Done - %f seconds" % (time.time()-start_time)


    def extend(self, target_info):
        if "name" in target_info:
            self.name = target_info["name"]

        if "type" in target_info:
            self.type = target_info["type"]

        if "includes" in target_info:
            self.includes += [pjoin(self.context.current_dir, i) for i in target_info["includes"]]

        if "sources_lists" in target_info:
            self.sources_lists += target_info["sources_lists"]
            for (index, list_id) in enumerate(self.sources_lists):
                if list_id in self.context.sources_lists_names:
                    self.sources_lists[index] = self.context.sources_lists_names[list_id]
                else:
                    if list_id < 0 or list_id >= len(self.context.sources_lists_names):
                        raise Exception("Invalid sources list id: "+str(list_id))

                    self.sources_list_index[index] = int(list_id)

        if "target_files" in target_info:
            self.target_files += processListOfFiles(target_info["target_files"], self.context.current_dir)

        if "sources" in target_info:
            self.sources += processListOfFiles(target_info["sources"], self.context.current_dir)

        if 'flags' in target_info:
            self.flags += asList(target_info['flags'])
        if 'compile_flags' in target_info:
            self.compile_flags += asList(target_info['compile_flags'])
        if 'link_flags' in target_info:
            self.link_flags += asList(target_info['link_flags'])

        self.pre_build_steps += parseListOfBuildSteps(target_info, self.context, "pre_build_steps")
        self.build_steps += parseListOfBuildSteps(target_info, self.context, "build_steps")
        self.post_build_steps += parseListOfBuildSteps(target_info, self.context, "post_build_steps")

        if "search_path" in target_info:
            self.cmake_search_path = target_info["search_path"]

        if "build_type" in target_info:
            self.build_type = target_info["build_type"]

        if "dependencies" in target_info:
            self.dependencies += [Context(parent_context=self.context, info=dependency).getTarget(dependency["name"]) for dependency in target_info["dependencies"]]

        if "build_dependencies" in target_info:
            self.build_dependencies += [Context(parent_context=self.context, info=dependency).getTarget(dependency["name"]) for dependency in target_info["build_dependencies"]]

        if "dependencies_dynamic_libs_destination_path" in target_info:
            self.dynamic_libs_destination_path = target_info["dependencies_dynamic_libs_destination_path"]
            self.linux_rpath = pjoin("$ORIGIN", self.dynamic_libs_destination_path)

        # Autoconf builds
        if self.build_type == "autoconf":
            autoconf_build_steps = [
                { "command": "./configure" },
                { "command": "make" }
            ]

            configure_command = autoconf_build_steps[0]
            make_command = autoconf_build_steps[1]

            # Run directory
            if "autoconf_directory" in target_info:
                configure_command["directory"] = target_info["autoconf_directory"]
                make_command["directory"] = target_info["autoconf_directory"]

            if "configure_directory" in target_info:
                configure_command["directory"] = target_info["configure_directory"]

            if "make_directory" in target_info:
                make_command["directory"] = target_info["make_directory"]

            # Commands parameters
            if "configure_params" in target_info:
                configure_command["params"] = target_info["configure_params"]

            if "make_params" in target_info:
                make_command["params"] = target_info["make_params"]

            for step in autoconf_build_steps:
                self.build_steps += [BuildStep(step, self.context)]


    def runBuildSteps(self, steps):
        for step in steps:
            step.run()

    def getAllDependenciesIncludesAndBinaries(self):
        includes = []
        binaries = []
        for dep in self.dependencies:
            (dep_includes, dep_binaries) = dep.getAllDependenciesIncludesAndBinaries()
            includes += [pjoin(dep.context.current_dir, i) for i in dep.includes]+dep_includes
            binaries += dep.target_files+dep_binaries

        return (includes, binaries)

    def process(self):
        self.build_folder = pjoin(self.context.build_folder, "__target_"+self.name)

        if not self.processed:
            if self.build_type == "cmake":
                self.processAsCMakeBuild()
            elif self.build_type == "crabsys":
                self.processAsCrabsysBuild()

            self.processed = True

    def processAsCMakeBuild(self):
        search_path = ''
        if self.cmake_search_path != "":
            search_path = pjoin(self.context.current_dir, self.cmake_search_path)

        self.generateCMakeListsFile(cmake_build_cmake_lists_template.format(
            project_name = self.name,
            name = self.name,
            upper_name = self.name.upper(),
            search_path=search_path,
            cmake_output_variables=cmake_output_variables
        ))

        output_values = run_cmake(self.build_folder)

        self.processCMakeOutputValues(output_values)

    def processAsCrabsysBuild(self):
        if len(self.sources) == 0 and len(self.sources_lists) == 0:
            return

        (dep_includes, dep_binaries) = self.getAllDependenciesIncludesAndBinaries()

        dynamic_libraries = []
        libs_dest_path = ""
        if self.type == 'executable' and len(self.dynamic_libs_destination_path) > 0:
            libs_dest_path = pjoin(self.context.current_dir,
                                   targets_relative_path,
                                   self.dynamic_libs_destination_path)
            libs_id_path = pjoin('@rpath', self.dynamic_libs_destination_path)

            for lib_path in dep_binaries:
                if is_dynamic_lib(lib_path):
                    lib_basename = os.path.basename(lib_path)

                    dynamic_libraries.append({
                        "new_lib_id": pjoin(libs_id_path, lib_basename),
                        "lib_original_path": lib_path,
                        "lib_destination_path": pjoin(libs_dest_path, lib_basename),
                    })

        self.generateCMakeListsFile(pystache.render(crabsys_build_cmake_lists_template,
            {
                'project_name': self.name,
                'name': self.name,
                'sources_lists_definitions': self.context.sources_lists,
                'dependencies_includes': dep_includes,
                'dependencies_binaries': dep_binaries,
                'sources': self.sources,
                'includes': self.includes,
                'executable': self.type == 'executable',
                'library': self.type == 'library',
                'sources_lists': self.sources_lists,
                'target_path': pjoin(self.context.current_dir, targets_relative_path),
                'linux_rpath': self.linux_rpath,
                'compile_flags': ' '.join(self.compile_flags+self.flags),
                'link_flags': ' '.join(self.link_flags+self.flags),
                'cmake_output_variables': cmake_output_variables,
                'dynamic_libraries_destination_path': libs_dest_path,
                'dynamic_libraries': dynamic_libraries
            }
        ))

        output_values = run_cmake(self.build_folder)

        self.processCMakeOutputValues(output_values)

        cpu_count = multiprocessing.cpu_count()
        if not self.parallel_build:
            cpu_count = 1

        self.build_steps += [BuildStep({
                'command': 'make',
                'directory': self.build_folder,
                'params': ['-j' + str(cpu_count)]
            }, self.context)]

    def generateCMakeListsFile(self, content):
        cmake_lists_file_path = pjoin(self.build_folder, 'CMakeLists.txt')

        if os.path.isfile(cmake_lists_file_path):
            if get_file_content(cmake_lists_file_path) == content:
                return
            if os.stat(cmake_lists_file_path).st_mtime > os.stat(self.context.getOriginalCrabFilePath()).st_mtime:
                return

        # Make sure the 'build' folder exists
        if not os.path.exists(self.build_folder):
            os.makedirs(self.build_folder)

        # Write CMakeLists.txt file with generated content
        cmake_file = open(cmake_lists_file_path, 'w')
        cmake_file.write(content)
        cmake_file.close()

    def processCMakeOutputValues(self, output_values):
        if "includes" in output_values:
            self.includes += [pjoin(self.context.current_dir, i) for i in output_values["includes"].split(";")]

        if "location" in output_values:
            self.target_files += output_values["location"].split(";")

    def shouldBuild(self):
        if self.build_type == "crabsys":
            return True

        for dep in self.dependencies:
            if dep.built:
                return True

        for target_file in self.target_files:
            target_file_path = pjoin(self.context.current_dir, target_file)

            if os.path.isfile(target_file_path):
                file_last_modification = os.stat(target_file_path).st_mtime
                crab_file_last_modification = os.stat(self.context.getOriginalCrabFilePath()).st_mtime

                if crab_file_last_modification > file_last_modification:
                    return True
            else:
                return True

        return False

    def build(self):
        if self.shouldBuild():
            self.runBuildSteps(self.pre_build_steps)
            self.runBuildSteps(self.build_steps)
            self.runBuildSteps(self.post_build_steps)

            self.built = True


class Context:
    def __init__(self, parent_context=None, info=None, directory=None):
        self.parent_context = parent_context

        if info:
            if 'repository' in info:
                if not self.parent_context:
                    raise Exception("Crab origin can't be a repository type build")
                directory = clone_repo(info['repository'],
                                       info.get('branch'),
                                       info.get('commit'),
                                       os.path.abspath(pjoin(self.parent_context.current_dir,
                                                             libraries_folder_relative_path)),
                                       crabsys_config["update_dependencies"])
            elif 'path' in info:
                if self.parent_context:
                    directory = pjoin(self.parent_context.current_dir, info["path"])
            elif 'cmake' in info:
                if 'name' not in info:
                    info['name'] = info['cmake']
                if 'search_path' in info and self.parent_context:
                    info["search_path"] = pjoin(self.parent_context.current_dir, info["search_path"])

                if self.parent_context:
                    directory = pjoin(self.parent_context.libs_dir, "cmake_dep_"+info['name'])
                    mkdir_p(directory)
            elif 'archive' in info:
                if not self.parent_context:
                    raise Exception("Crab origin can't be a archive type build")
                directory = retrieve_archive(info.get('archive'),
                                             info.get('archive_file_name'),
                                             self.parent_context.libs_dir)
                directory = pjoin(directory, info.get('archive_path', ''))

        if not directory:
            directory = "."

        self.current_dir = os.path.abspath(directory)
        self.libs_dir = pjoin(self.current_dir, libraries_folder_relative_path)
        self.build_folder = pjoin(self.current_dir, build_folder_relative_path)

        self.cmake_lists_file_path = pjoin(self.build_folder, 'CMakeLists.txt')

        self.current_target = None
        self.dynamic_libs = []

        self.level = 0
        if self.parent_context:
            self.level = parent_context.level+1

        self.build_info = info
        if self.build_info is None:
            self.build_info = {}

        if "type" in self.build_info:
            self.build_type = self.build_info["type"]

            if self.build_type in build_types:
                self.build_type = build_type[self.build_type]
        elif "cmake" in self.build_info:
            self.build_type = "cmake"
        else:
            self.build_type = "crabsys"

        self.build_info["build_type"] = self.build_type

        if self.build_type == "crabsys":
            self.processCrabFile(self.build_info)

        if 'project_name' not in self.build_info:
            if self.build_type == "crabsys":
                print directory + ': project name not defined, using folder name'
            self.build_info['project_name'] =\
                os.path.basename(os.path.dirname(directory+os.sep))

        self.project_name = self.build_info['project_name']

        if parent_context is not None:
            self.global_context = parent_context.global_context
        else:
            self.global_context = GlobalContext()

        self.already_processed = self.global_context.add_project(self.project_name, self)

        self.children = []
        if self.parent_context:
            self.parent_context.addChildContext(self)

        self.sources_lists_names = {}
        self.sources_lists = []
        if 'sources_lists' in self.build_info:
            self.sources_lists = self.build_info['sources_lists']
            for index, sources_list in enumerate(self.sources_lists):
                sources_list['index'] = index
                if 'name' in sources_list:
                    self.sources_lists_names[sources_list['name']] = index
                if 'sources' in sources_list:
                    sources_list["sources"] = processListOfFiles(sources_list["sources"], self.current_dir)

        if "targets" in self.build_info:
            self.targets = [Target(info, self) for info in self.build_info["targets"]]
        else:
            self.targets = [Target(self.build_info, self)]

    def getTarget(self, target_name):
        for t in self.targets:
            if t.name == target_name:
                return t

        return None

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

    def getOriginalCrabFilePath(self):
        if self.build_type == "crabsys" and os.path.isfile(self.crab_file_path):
            return os.path.abspath(self.crab_file_path)
        elif self.parent_context:
            return self.parent_context.getOriginalCrabFilePath()
        else:
            print "Warning: No crab file found! This shouldn't happen!"
            return None
