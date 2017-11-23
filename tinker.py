#!/usr/bin/env python

# A throwaway program for testing ideas.

import os
import subprocess

DEVNULL = open(os.devnull, 'w')
procList = list()

procList.append(subprocess.Popen("smartctl -a /dev/sda".split(), stdout=subprocess.PIPE, stderr=DEVNULL))

exitFlag = False
while not exitFlag:
    for proc in procList:
        status = proc.poll()

        if status is not None:
            print "Process complete, status is " + str(status)
            output, _ = proc.communicate()
            print output
            exitFlag = True
        else:
            print "."
