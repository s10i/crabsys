#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path
import subprocess
import time
import shutil
import argparse


##############################################################################
examples = [
    {
        "path": "example01",
        "target": "a.out",
        "type": "executable",
        "output": "CRABSYS RULEZ!!!11\n"
    },
    {
        "path": "example02",
        "target": "a.out",
        "type": "executable",
        "output": "CRABSYS RULEZ!!!11\n1\n2\n3\n"
    },
    {
        "path": "example03",
        "target": "libcrablib.a",
        "type": "library"
    },
    {
        "path": "example04",
        "target": "example04",
        "type": "executable",
        "output": "CRAB RULEZ!!!11\n3\n"
    },
    {
        "path": "example05",
        "target": "test.run",
        "type": "executable",
        "output": "MySQL dependency test\n"
    },
    {
        "path": "example06",
        "target": "main.run",
        "type": "executable",
        "output": """CRAB rulez!!
<!doctype html>
<html>
<head>
    <title>Example Domain</title>

    <meta charset="utf-8" />
    <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style type="text/css">
    body {
        background-color: #f0f0f2;
        margin: 0;
        padding: 0;
        font-family: "Open Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
        
    }
    div {
        width: 600px;
        margin: 5em auto;
        padding: 50px;
        background-color: #fff;
        border-radius: 1em;
    }
    a:link, a:visited {
        color: #38488f;
        text-decoration: none;
    }
    @media (max-width: 700px) {
        body {
            background-color: #fff;
        }
        div {
            width: auto;
            margin: 0 auto;
            border-radius: 0;
            padding: 1em;
        }
    }
    </style>    
</head>

<body>
<div>
    <h1>Example Domain</h1>
    <p>This domain is established to be used for illustrative examples in documents. You may use this
    domain in examples without prior coordination or asking for permission.</p>
    <p><a href="http://www.iana.org/domains/example">More information...</a></p>
</div>
</body>
</html>
CRAB rulez!!
"""
    }

]

REPLAY_MAX_TIME = 1.0
CRAB_PATH = os.path.abspath("../crabsys/crabsys.py")
##############################################################################


##############################################################################
def testExamples(examples, keep):
    for e in examples:
        testExample(e, keep)

def testExample(example, keep):

    build_folder = os.path.join( example["path"], example.get("build_folder", "build") )
    libs_folder = os.path.join( example["path"], example.get("libs_folder", "libs") )

    if os.path.exists(build_folder) and not keep:
        shutil.rmtree(build_folder)
    
    if os.path.exists(libs_folder) and not keep:
        shutil.rmtree(libs_folder)

    # First run
    p = subprocess.Popen(["python", CRAB_PATH], cwd=example["path"], stdout=subprocess.PIPE)
    p_output = p.communicate()[0]
    if p.returncode != 0:
        print "Error running crabsys at: ", example["path"]
        print p_output
        exit(4)


    # Checks
    target_path = os.path.abspath( os.path.join( build_folder, example["target"] ) )

    if not os.path.exists( target_path ):
        print "Target not found: ", target_path
        exit(1)

    if not os.path.isfile( target_path ):
        print "Target is not a file: ", target_path
        exit(2)

    if example["type"] == "executable":
        output = subprocess.check_output([ target_path ], cwd=example["path"])
        if output != example["output"]:
            print "Unexpected output:"
            print output
            exit(3)


    # Timed replay
    start_time = time.time()

    p = subprocess.Popen(["python", CRAB_PATH], cwd=example["path"], stdout=subprocess.PIPE)
    p_output = p.communicate()[0]
    if p.returncode != 0:
        print "Error running crabsys at: ", example["path"]
        print p_output
        exit(4)
    
    elapsed_time = time.time() - start_time

    if elapsed_time > REPLAY_MAX_TIME:
        print "Replay took too long: %lf (%s)" % (elapsed_time, example["path"])
##############################################################################




##############################################################################
def main():
    parser = argparse.ArgumentParser(description='CRABsys Examples Tester')
    parser.add_argument('--keep', action='store_true', dest='keep', default=False,
                        help="Keep build and dependencies folders (don't delete them before the first run). Useful for quick testing during development.")

    args = parser.parse_args()

    #print args

    testExamples(examples, keep=args.keep)
##############################################################################


##############################################################################
if __name__ == "__main__":
    main()
##############################################################################

