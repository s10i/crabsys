
# CRABSys - C/C++ Recursive Automated Build System
(spoken as 'crab' or 'crabs' pronounced by Gollum)

CRABSys is a tool for recursively building C/C++ projects,
with help from CMake.

To build a project, just use the command:

    crab build

In the folder where the *crab.json* specification file is placed.

## Installation

Using pip:
    pip install git+https://github.com/s10i/crabsys.git

Note for Mac users: if you use pip/python from macports, pip installs
binaries at an inaccessible location (not in the PATH). Usually I just
link it to /opt/local/bin (macports binaries folder) with something like:
    cd /opt/local/bin; ln -s . /opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin/crab


