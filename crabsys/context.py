
import os
import json
import glob

from os.path import join as pjoin
from utils import get_file_content

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


class GlobalContext:
    def __init__(self):
        self.projects = {}

    def add_project(self, project_name, context):
        if project_name in self.projects:
            return self.projects[project_name].current_dir == context.current_dir
        else:
            self.projects[project_name] = context
            return False

class Context:
    def __init__(self, build_info, current_dir, parent_context, process_function):
        self.current_dir = current_dir
        self.parent_context = parent_context
        self.libs_dir = pjoin(current_dir, libraries_folder_relative_path)
        self.build_folder = pjoin(current_dir, build_folder_relative_path)
        self.cmake_lists_file_path = pjoin(self.build_folder, 'CMakeLists.txt')

        self.process = process_function

        self.current_target = None
        self.dynamic_libs = []

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

    def processCrabFile(self, build_info):
        crab_file_path = pjoin(self.current_dir, 'crab.json')

        try:
            cmake_file_last_modification = os.stat(self.cmake_lists_file_path).st_mtime
            crab_file_last_modification = os.stat(crab_file_path).st_mtime

            #if crab_file_last_modification < cmake_file_last_modification:
            #    return
        except OSError, e:
            pass

        if crab_file_path:
            if os.path.isfile(crab_file_path):
                # Read crab file and parse as json
                self.build_info = json.loads(get_file_content(crab_file_path))
            else:
                print "crab.json file not found - setting to default build"
                self.build_info = {
                    "targets": [
                        {
                            "name": "a.out",
                            "type": "executable",
                            "sources": glob.glob(pjoin(self.current_dir, "*.cpp"))+
                                       glob.glob(pjoin(self.current_dir, "*.c"))+
                                       glob.glob(pjoin(self.current_dir, "src", "*.cpp"))+
                                       glob.glob(pjoin(self.current_dir, "src", "*.c"))
                        }
                    ]
                }
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

        # Make sure the 'build' folder exists
        if not os.path.exists(self.build_folder):
            os.makedirs(self.build_folder)

        # Write CMakeLists.txt file with generated content
        cmake_file = open(self.cmake_lists_file_path, 'w')
        cmake_file.write(cmake_file_content)
        cmake_file.close()
