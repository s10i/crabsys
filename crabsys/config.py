
from __future__ import unicode_literals

import json
import errno
import os

config_files_locations = [
    "/etc/crabsys/crabsys.config.json",
    "~/.crabsys/crabsys.config.json",
    "~/.crabsys.config.json",
    ".crabsys/crabsys.config.json",
    ".crabsys.config.json"
]

crabsys_config = {
    "compile_flags": "-Wall",
    "link_flags": "",
    "includes": [
        "."
    ],
    "default_build": {
        "targets": [
            {
                "name": "a.out",
                "type": "executable",
                "sources": [
                    { "glob": "*.cpp" },
                    { "glob": "*.c" },
                    { "glob": "src/*.cpp" },
                    { "glob": "src/*.c" }
                ]
            }
        ]
    }
}


def mergeDictionary(target, source):
    for key in source:
        if key in target:
            target[key] = mergeValue(target[key], source[key])
        else:
            target[key] = source[key]

    return target


def mergeValue(target, source):
    if type(target) != type(source):
        print "Warning: target and source types differ: %s != %s" % (type(target), type(source))
        return source

    if type(target) == type({}):
        return mergeDictionary(target, source)
    else:
        return source


def mergeConfig(config):
    mergeDictionary(crabsys_config, config)


def loadConfiguration():
    for path in config_files_locations:
        try:
            mergeConfig(json.load(open(path)))
        except IOError as e:
            if e.errno != 2:
                print "Warning: error opening config file: %s" % (path)
                print 'errno:', e.errno
                print 'err code:', errno.errorcode[e.errno]
                print 'err message:', os.strerror(e.errno)

    print crabsys_config
