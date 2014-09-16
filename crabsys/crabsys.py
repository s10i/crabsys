#!/usr/bin/env python

import argparse
import os.path

from context import Context
from config import loadConfiguration


#############################################################################
def parseArguments():
    parser = argparse.ArgumentParser(description='C/C++ Recursive Automated Build System')
    parser.add_argument('--update-dependencies', action='store_true', dest='update_dependencies', default=None,
                        help='Update all repository dependencies before building')
    parser.add_argument('--dont-update-dependencies', action='store_false', dest='update_dependencies', default=None,
                        help='DO NOT update any repository dependencies before building')
    parser.add_argument('--config', metavar='CONFIG', action='store', dest='config_file_path',
                        help='Configuration file path')
    parser.add_argument('--path', metavar='PATH', action='store', dest='path', default='.',
                        help='Path of where the processing should start')
    parser.add_argument('action', default='build', nargs='?',
                        help='Crabsys action (only build is supported for now)')

    args = parser.parse_args()

    #print args

    return args

def main():
    args = parseArguments()

    args_config = {}
    if args.update_dependencies:
        args_config["update_dependencies"] = args.update_dependencies

    loadConfiguration(args.config_file_path, args_config)

    if args.action == 'build':
        context = Context(directory=os.path.abspath(args.path))

        for target in context.targets:
            target.process()
            target.build()
    else:
        print "Action not supported: %s" % (args.action)
#############################################################################



if __name__ == '__main__':
    main()
