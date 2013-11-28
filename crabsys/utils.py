
import os
import subprocess
import tarfile
import errno
import os.path

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

def add_path_prefix_and_join(values, prefix, separator):
    return separator.join([pjoin(prefix, value) for value in values])

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def system_command(params=None, directory=None):
    original_working_directory = os.getcwd()

    os.chdir(directory)
    return_code = subprocess.call(params, shell=False)

    os.chdir(original_working_directory)

    return return_code

def git_command(params=None, directory=None):
    return system_command(['git'] + params, directory)

def git_clone(url, directory=None):
    if git_command(params=['clone', url], directory=directory) != 0:
        raise Exception('Error cloning repository: ' + url)

def git_status(directory=None):
    if git_command(params=['status'], directory=directory) != 0:
        raise Exception('Error getting repository status: ' + directory)

def git_pull(directory=None):
    if git_command(params=['pull'], directory=directory) != 0:
        raise Exception('Error running git pull: ' + directory)
