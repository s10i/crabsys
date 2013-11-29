
import os
import os.path
import urllib
import tarfile
from urlparse import urlparse
from os.path import join as pjoin

from context import build_folder_relative_path, targets_relative_path, libraries_folder_relative_path
from utils import *
from templates import *

#############################################################################
## Dependencies ##
##################
def process_cmake_dependency(dependency_info, context):
    name = dependency_info['cmake']
    #context.append_cmake_dependency(context.current_target,
    #                                '${' + name.upper() + '_INCLUDE_DIR}',
    #                                '${' + name.upper() + '_LIBRARIES}')

    search_path_include = ''
    if 'search_path' in dependency_info:
        search_path = pjoin(context.current_dir,
                            dependency_info['search_path'])
        search_path_include = cmake_dependency_search_path_template.format(
                search_path=search_path
            )

    return search_path_include + cmake_dependency_template.format(name=name,
                                    upper_name=name.upper(),
                                    prefix=context.current_target['name'])

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
        build_folder_relative_path)

    context.process(dependency_absolute_path, dependency_info, context)

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
    elif 'archive' in dependency_info:
        return process_archive_dependency(dependency_info, context)

    return ''

def process_dependencies(target_info, context):
    dependencies_includes = ''
    context.init_cmake_dependencies(target_info)

    if 'dependencies' in target_info:
        for dependency in target_info['dependencies']:
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
                                     targets_relative_path,
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
