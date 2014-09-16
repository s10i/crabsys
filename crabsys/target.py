
# STD Library
import time
import os
import sys
from os.path import join as pjoin

# External dependencies
import pystache

# Internal dependencies
from build_step import parseListOfBuildSteps, BuildStep
from utils import *
from config import crabsys_config


##############################################################################
class Target:
    def __init__(self, target_info, context):
        self.context = context

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

        self.dependencies_infos = []
        self.build_dependencies_infos = []

        self.linux_rpath = ""
        self.dynamic_libs_destination_path = ""

        self.extend(target_info)

        for system in target_info.get('system_specific', {}):
            platform = system
            if system in platform_names:
                platform = platform_names[system]

            if platform == sys.platform:
                self.extend(target_info.get('system_specific')[system])


    def extend(self, target_info):
        if self.name is None:
            self.name = target_info.get("name", os.path.basename(self.context.current_dir))
        if self.type is None:
            self.type = target_info.get("type")

        self.includes += [pjoin(self.context.current_dir, i) for i in target_info.get("includes", [])]

        self.sources_lists += target_info.get("sources_lists", [])
        for (index, list_id) in enumerate(self.sources_lists):
            if list_id in self.context.sources_lists_names:
                self.sources_lists[index] = self.context.sources_lists_names[list_id]
            else:
                if list_id < 0 or list_id >= len(self.context.sources_lists_names):
                    raise Exception("Invalid sources list id: "+str(list_id))

                self.sources_list_index[index] = int(list_id)

        self.target_files += processListOfFiles(target_info.get("target_files", []), self.context.current_dir)
        self.sources += processListOfFiles(target_info.get("sources", []), self.context.current_dir)

        self.flags += asList(target_info.get('flags', []))
        self.compile_flags += asList(target_info.get('compile_flags', crabsys_config["compile_flags"]))
        self.link_flags += asList(target_info.get('link_flags', crabsys_config["link_flags"]))

        self.pre_build_steps += parseListOfBuildSteps(target_info, self.context, "pre_build_steps")
        self.build_steps += parseListOfBuildSteps(target_info, self.context, "build_steps")
        self.post_build_steps += parseListOfBuildSteps(target_info, self.context, "post_build_steps")

        self.cmake_search_path = target_info.get("search_path", "")

        self.build_type = target_info.get("build_type", self.build_type)

        self.dependencies_infos += target_info.get("dependencies", [])
        self.build_dependencies_infos += target_info.get("build_dependencies", [])

        self.dynamic_libs_destination_path = target_info.get("dependencies_dynamic_libs_destination_path", "")
        self.linux_rpath = pjoin("$ORIGIN", self.dynamic_libs_destination_path)

        # Autoconf builds
        if self.build_type == "autoconf":
            autoconf_directory = target_info.get("autoconf_directory", "")

            self.build_steps += [
                BuildStep({
                    "command": "./configure",
                    "directory": target_info.get("configure_directory", autoconf_directory),
                    "params": target_info.get("configure_params", [])
                }, self.context),
                BuildStep({
                    "command": "make",
                    "directory": target_info.get("make_directory", autoconf_directory),
                    "params": target_info.get("make_params", [])
                }, self.context)
            ]


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
        start_time = time.time()
        print ("--"*self.context.level) + "-> Processing # %s #" % (self.name)

        self.dependencies = [self.context.getContext(parent_context=self.context, info=dependency).getTarget(dependency["name"]) for dependency in self.dependencies_infos]
        self.build_dependencies = [self.context.getContext(parent_context=self.context, info=dependency).getTarget(dependency["name"]) for dependency in self.build_dependencies_infos]

        for dependency in self.dependencies:
            dependency.process()

        for dependency in self.build_dependencies:
            dependency.process()

        self.build_folder = pjoin(self.context.build_folder, "__target_"+self.name)

        if not self.processed:
            if self.build_type == "cmake":
                self.processAsCMakeBuild()
            elif self.build_type == "crabsys":
                self.processAsCrabsysBuild()

            self.processed = True

        print ("--"*self.context.level) + "-> Done - %f seconds" % (time.time()-start_time)


    def processAsCMakeBuild(self):
        search_path = ""
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

        print self.build_folder
        print self.type
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
            if ( self.context.getOriginalCrabFilePath() is not None and
                 os.stat(cmake_lists_file_path).st_mtime > os.stat(self.context.getOriginalCrabFilePath()).st_mtime ):
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
            print "Because CRABSYS!!!"
            return True
        elif self.build_type == "cmake":
            return False

        for dep in self.dependencies:
            if dep.built:
                print "Because dependency was just built"
                return True

        for target_file in self.target_files:
            target_file_path = pjoin(self.context.current_dir, target_file)

            if os.path.isfile(target_file_path):
                file_last_modification = os.stat(target_file_path).st_mtime
                crab_file_last_modification = os.stat(self.context.getOriginalCrabFilePath()).st_mtime

                if crab_file_last_modification > file_last_modification:
                    print "Because of the file modification dates"
                    print "Original crab file modification time: ", crab_file_last_modification
                    print "Target file modification time (%s): %d" % ( target_file_path, file_last_modification )
                    return True
            else:
                return True

        return False

    def build(self):
        print "Shoud build?"
        if self.shouldBuild():
            print "Yes, please"
            self.runBuildSteps(self.pre_build_steps)
            self.runBuildSteps(self.build_steps)
            self.runBuildSteps(self.post_build_steps)

            self.built = True
##############################################################################
