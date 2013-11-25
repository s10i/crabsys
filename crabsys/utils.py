
import os
import subprocess

from os.path import join as pjoin

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
