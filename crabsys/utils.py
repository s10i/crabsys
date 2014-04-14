
import os
import subprocess
import tarfile
import errno
import os.path
import glob
import re
import multiprocessing
import urllib
from urlparse import urlparse

from sys import stderr
from os.path import join as pjoin

##############################################################################
# TAR FILES HANDLING
resolved = lambda x: os.path.realpath(os.path.abspath(x))

def badpath(path, base):
    # joinpath will ignore base if path is absolute
    return not resolved(pjoin(base,path)).startswith(base)

def badlink(info, base):
    # Links are interpreted relative to the directory containing the link
    tip = resolved(pjoin(base, dirname(info.name)))
    return badpath(info.linkname, base=tip)

def safemembers(members):
    base = resolved(".")

    for finfo in members:
        if badpath(finfo.name, base):
            print >>stderr, finfo.name, "is blocked (illegal path)"
        elif finfo.issym() and badlink(finfo,base):
            print >>stderr, finfo.name, "is blocked: Hard link to", finfo.linkname
        elif finfo.islnk() and badlink(finfo,base):
            print >>stderr, finfo.name, "is blocked: Symlink to", finfo.linkname
        else:
            yield finfo
##############################################################################


def retrieve_archive(archive_url, file_name, directory):
    if not file_name:
        file_name = os.path.basename(urlparse(archive_url).path)

    archive_file_path = pjoin(directory, file_name)
    extracted_dir = pjoin(directory, archive_file_path+"_extracted")

    if not os.path.isfile(archive_file_path):
        mkdir_p(directory)
        urllib.urlretrieve (archive_url, archive_file_path)

        if not os.path.isdir(extracted_dir):
            archive = tarfile.open(archive_file_path)
            archive.extractall(path=extracted_dir, members=safemembers(archive))

    return extracted_dir


def encapsulate(value):
    if value is None:
        return []

    if not isinstance(value, list):
        return [value]

    return value

asList = encapsulate

def processListOfFiles(files_list, prefix_path, allowGlobs=False):
    return_list = []

    for file_path in asList(files_list):
        if type(file_path)==type({}):
            if 'glob' in file_path:
                glob_sources = glob.glob(pjoin(prefix_path, file_path['glob']))

                return_list += glob_sources
        else:
            return_list += [pjoin(prefix_path, file_path)]

    return return_list


def get_file_content(file_path):
    file_handle = open(file_path, 'r')
    content = file_handle.read()
    file_handle.close()
    return content

def extract_repository_name_from_url(repo_url):
    last_slash_index = repo_url.rfind('/')
    repo_name = repo_url[last_slash_index+1:]

    if repo_name[-4:] == '.git':
        repo_name = repo_name[:-4]

    return repo_name

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def system_command(params=None, directory=None):
    process = subprocess.Popen(params,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               cwd=directory,
                               shell=False)

    stdout, stderr = process.communicate()

    retcode = process.poll()

    return (retcode, stdout, stderr)



def is_dynamic_lib(path):
    return re.match("^(.*)\.dylib", path) or re.match("^(.*)\.so(\.[0-9]*)?", path)


cmake_output_variables = {
    "location": "__crabsys_target_location",
    "includes": "__crabsys_target_includes"
}

def run_cmake(directory=None):
    (retcode, stdout, stderr) = system_command(['cmake', '.'], directory)

    if retcode != 0:
        print stderr
        return None

    output_values = {}
    for line in stderr.split('\n'):
        for (key,variable) in cmake_output_variables.iteritems():
            if line.startswith(variable+'='):
                value = line[len(variable+'='):]
                output_values[key] = value

    return output_values




##############################################################################
## GIT UTILITIES #############################################################
##############################################################################
def git_command(params=None, directory=None):
    return system_command(['git'] + params, directory)

def git_clone(url, directory=None):
    (retcode, stdout, stderr) = git_command(params=['clone', url], directory=directory)
    if retcode != 0:
        raise Exception('Error cloning repository: ' + url + '\n' + stderr)

def git_checkout(branch_or_commit, directory=None):
    (retcode, stdout, stderr) = git_command(params=['checkout', branch_or_commit], directory=directory)
    if retcode != 0:
        raise Exception('Error checkouting repository: ' + url + '\n' + stderr)

def git_status(directory=None):
    (retcode, stdout, stderr) = git_command(params=['status'], directory=directory)
    if retcode != 0:
        raise Exception('Error getting repository status: ' + directory + '\n' + stderr)

def git_pull(directory=None):
    (retcode, stdout, stderr) = git_command(params=['pull'], directory=directory)
    if retcode != 0:
        raise Exception('Error running git pull: ' + directory + '\n' + stderr)


def clone_repo(url, branch, commit, destination_path, force_update=False):
    repo_name = extract_repository_name_from_url(url)

    dependency_absolute_path = pjoin(destination_path, repo_name)

    if os.path.exists(dependency_absolute_path):
        if os.path.isdir(dependency_absolute_path):
            git_status(directory=dependency_absolute_path)
            if force_update:
                git_pull(directory=dependency_absolute_path)
        else:
            raise Exception('Repository path exists but is not' +\
                            ' a directory: ' + dependency_absolute_path)
    else:
        mkdir_p(os.path.abspath(destination_path))

        git_clone(url, directory=destination_path)

        if branch:
            git_checkout(branch, directory=dependency_absolute_path)
        elif commit:
            git_checkout(commit, directory=dependency_absolute_path)

    return dependency_absolute_path
##############################################################################

