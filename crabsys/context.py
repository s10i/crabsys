
import os
import json
import copy

from os.path import join as pjoin
from config import crabsys_config
from utils import *
from target import createTarget


##############################################################################
class GlobalContext:
    def __init__(self):
        self.projects = {}

    def add_project(self, project_name, context):
        if project_name in self.projects:
            return self.projects[project_name].current_dir == context.current_dir
        else:
            self.projects[project_name] = context
            return False
##############################################################################



##############################################################################
context_cache = {}

def getContext(parent_context, info):
    directory = None

    if info:
        if 'repository' in info:
            if not parent_context:
                raise Exception("Crab origin can't be a repository type build")
            directory = clone_repo(info['repository'],
                                   info.get('branch'),
                                   info.get('commit'),
                                   os.path.abspath(pjoin(parent_context.current_dir,
                                                         libraries_folder_relative_path)),
                                   crabsys_config["update_dependencies"])
        elif 'path' in info:
            if parent_context:
                directory = pjoin(parent_context.current_dir, info["path"])
        elif 'cmake' in info:
            if 'name' not in info:
                info['name'] = info['cmake']
            if 'search_path' in info and parent_context:
                info["search_path"] = pjoin(parent_context.current_dir, info["search_path"])

            if parent_context:
                directory = pjoin(parent_context.libs_dir, "cmake_dep_"+info['name'])
                mkdir_p(directory)
        elif 'archive' in info:
            if not parent_context:
                raise Exception("Crab origin can't be a archive type build")
            directory = retrieve_archive(info.get('archive'),
                                         info.get('archive_file_name'),
                                         parent_context.libs_dir)
            directory = pjoin(directory, info.get('archive_path', ''))

    if not directory:
        directory = "."

    context_dir = os.path.abspath(directory)

    if context_dir in context_cache:
        return context_cache[context_dir]
    else:
        return Context(parent_context=parent_context, info=info, directory=context_dir)
##############################################################################
##############################################################################



##############################################################################
class Context:
    def __init__(self, parent_context=None, info=None, directory=None):
        self.parent_context = parent_context
        self.current_dir = os.path.abspath(directory)

        self.getContext = getContext

        context_cache[self.current_dir] = self

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
                self.build_type = build_types[self.build_type]
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
            self.targets = []

            # Can't use list comprehension here because it breaks
            # intra-context dependencies
            for info in self.build_info["targets"]:
                self.targets.append(createTarget(info, self))
        else:
            self.targets = [createTarget(self.build_info, self)]


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
##############################################################################

