
import os
import json

from os.path import join as pjoin
from utils import get_file_content

build_folder_relative_path = pjoin('build', '.build')
targets_relative_path = 'build'

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
    def __init__(self, current_dir, crab_file_path, parent_context, process_function):
        self.current_dir = current_dir
        self.parent_context = parent_context
        self.cmake_libraries = {}
        self.cmake_includes = {}
        self.current_target = None
        self.crab_file_path = crab_file_path
        self.dynamic_libs = []
        self.process = process_function

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
