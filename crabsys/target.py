
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
def createTarget(target_info, context):
    if target_info.get("build_type") == "autoconf":
        return AutoconfTarget(target_info, context)
    elif target_info.get("build_type") == "cmake":
        return CMakeTarget(target_info, context)
    elif target_info.get("build_type") == "custom":
        return CustomBuildTarget(target_info, context)

    return CrabsysTarget(target_info, context)
##############################################################################



##############################################################################
class BaseTarget(object):
    def __init__(self, target_info, context):
        self.context = context
        self.info = target_info
        self.platform_info = {}

        self.processed = False

        self.name = None
        self.type = None

        self.includes = []
        self.target_files = []

        self.build_steps = []
        self.pre_build_steps = []
        self.post_build_steps = []

        self.built = False

        self.dependencies_infos = []
        self.build_dependencies_infos = []

        self.extend(target_info)

        for system in target_info.get('system_specific', {}):
            platform = system
            if system in platform_names:
                platform = platform_names[system]

            if platform == sys.platform:
                self.extend(target_info.get('system_specific')[system])
                self.platform_info = target_info.get('system_specific')[system]


    def extend(self, target_info):
        if self.name is None:
            self.name = target_info.get("name", os.path.basename(self.context.current_dir))
        if self.type is None:
            self.type = target_info.get("type")

        self.includes += [pjoin(self.context.current_dir, i) for i in target_info.get("includes", [])]
        self.target_files += processListOfFiles(target_info.get("target_files", []), self.context.current_dir)

        self.pre_build_steps += parseListOfBuildSteps(target_info, self.context, "pre_build_steps")
        self.build_steps += parseListOfBuildSteps(target_info, self.context, "build_steps")
        self.post_build_steps += parseListOfBuildSteps(target_info, self.context, "post_build_steps")

        self.dependencies_infos += target_info.get("dependencies", [])
        self.build_dependencies_infos += target_info.get("build_dependencies", [])


    def runBuildSteps(self, steps):
        for step in steps:
            step.run()

    def process(self):
        start_time = time.time()
        print ("| "*self.context.level) + "-> Processing # %s #" % (self.name)

        self.dependencies = [
            self.context.getContext( parent_context=self.context,
                                     info=dependency )
                .getTarget(dependency["name"])

            for dependency in self.dependencies_infos
        ]

        self.build_dependencies = [
            self.context.getContext( parent_context=self.context,
                                     info=dependency)
                .getTarget(dependency["name"])

            for dependency in self.build_dependencies_infos
        ]

        for dependency in self.dependencies:
            dependency.process()

        for dependency in self.build_dependencies:
            dependency.process()
            dependency.build()

        self.runBuildSteps(self.pre_build_steps)

        self.build_folder = pjoin(self.context.build_folder, "__target_"+self.name)

        if not self.processed:
            self._process()
            self.processed = True

        print ("| "*self.context.level) + "-> Done - %f seconds" % (time.time()-start_time)


    def shouldBuild(self):
        for dep in self.dependencies:
            if dep.built:
                #print "Because dependency was just built"
                return True

        for target_file in self.target_files:
            target_file_path = pjoin(self.context.current_dir, target_file)

            if os.path.isfile(target_file_path):
                file_last_modification = os.stat(target_file_path).st_mtime
                crab_file_last_modification = os.stat(self.context.getOriginalCrabFilePath()).st_mtime

                if crab_file_last_modification > file_last_modification:
                    #print "Because of the file modification dates"
                    #print "Original crab file modification time: ", crab_file_last_modification
                    #print "Target file modification time (%s): %d" % ( target_file_path, file_last_modification )
                    return True
            else:
                return True

        return False

    def build(self):
        start_time = time.time()
        print ("| "*self.context.level) + "-> Building # %s #" % (self.name)

        for dependency in self.dependencies:
            dependency.build()

        if self.shouldBuild():
            self.runBuildSteps(self.build_steps)
            self.built = True

        self.runBuildSteps(self.post_build_steps)
        self.postBuild()

        print ("| "*self.context.level) + "-> Done - %f seconds" % (time.time()-start_time)

    def postBuild(self):
        pass

    def getAllDependenciesIncludesAndBinaries(self):
        includes = []
        binaries = []
        for dep in self.dependencies:
            (dep_includes, dep_binaries) = dep.getAllDependenciesIncludesAndBinaries()
            includes += [pjoin(dep.context.current_dir, i) for i in dep.includes]+dep_includes
            binaries += dep.target_files+dep_binaries

        return (includes, binaries)
##############################################################################



##############################################################################
class AutoconfTarget(BaseTarget):
    def __init__(self, target_info, context):
        super(AutoconfTarget, self).__init__(target_info, context)

        autoconf_directory = target_info.get("autoconf_directory", "")

        self.build_steps = [
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

    def _process(self):
        pass

    def postBuild(self):
        for target_file in self.target_files:
            with open(target_file, 'a'):
                os.utime(target_file, None)
##############################################################################



##############################################################################
class CrabsysTarget(BaseTarget):
    def __init__(self, target_info, context):
        super(CrabsysTarget, self).__init__(target_info, context)

        self.parallel_build = True

        # Flags initialization
        def joinedOrDefault(name, dict1, dict2, defaults):
            l = asList(dict1.get(name, []))+asList(dict2.get(name, []))
            if len(l) == 0:
                return asList(defaults.get(name, []))
            return l

        self.flags = joinedOrDefault( 'flags', self.info, self.platform_info,
            crabsys_config )
        self.compile_flags = joinedOrDefault( 'compile_flags', self.info,
            self.platform_info, crabsys_config )
        self.link_flags = joinedOrDefault( 'link_flags', self.info,
            self.platform_info, crabsys_config )

        # Sources initialization
        self.sources_lists = self.info.get("sources_lists", [])
        self.sources_lists += self.platform_info.get("sources_lists", [])

        self.sources = processListOfFiles(self.info.get("sources", []), self.context.current_dir)
        self.sources += processListOfFiles(self.platform_info.get("sources", []), self.context.current_dir)

        # Dynamic libs info initialization
        self.dynamic_libs_destination_path = self.info.get(
            "dependencies_dynamic_libs_destination_path",
            self.platform_info.get("dependencies_dynamic_libs_destination_path",
                "")
        )
        self.linux_rpath = pjoin( "$ORIGIN", self.dynamic_libs_destination_path )


    def _process(self):
        self.processAsCrabsysBuild()


    def processAsCrabsysBuild(self):
        if len(self.sources) == 0 and len(self.sources_lists) == 0:
            return

        # Process sources lists
        for (index, list_id) in enumerate(self.sources_lists):
            if list_id in self.context.sources_lists_names:
                self.sources_lists[index] = self.context.sources_lists_names[list_id]
            else:
                if list_id < 0 or list_id >= len(self.context.sources_lists_names):
                    raise Exception("Invalid sources list id: "+str(list_id))

                self.sources_list_index[index] = int(list_id)

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
        return True

    def postBuild(self):
        for target_file in self.target_files:
            with open(target_file, 'a'):
                os.utime(target_file, None)
##############################################################################



##############################################################################
class CMakeTarget(BaseTarget):
    def __init__(self, target_info, context):
        super(CMakeTarget, self).__init__(target_info, context)

        self.cmake_search_path = self.info.get("search_path",
            self.platform_info.get("search_path", "") )

    def _process(self):
        self.processAsCMakeBuild()

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

    def shouldBuild(self):
        return False
##############################################################################



##############################################################################
class CustomBuildTarget(BaseTarget):
    def __init__(self, target_info, context):
        super(CustomBuildTarget, self).__init__(target_info, context)

    def _process(self):
        pass

    def postBuild(self):
        for target_file in self.target_files:
            with open(target_file, 'a'):
                os.utime(target_file, None)
##############################################################################

