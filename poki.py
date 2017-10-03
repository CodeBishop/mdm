#!/usr/bin/env python

import re
import subprocess
import os

# Fetch the null device for dumping unsightly error messages into.
DEVNULL = open(os.devnull, 'w')


# Program definition.
def main():
    haltWithoutRootAuthority();
    print "Hello"
    print terminalCommand('ls /dev')


# Call a root-only command to test if the user has admin authority.
def haltWithoutRootAuthority():
    try:
        proc = subprocess.Popen(["sudo", "dmidecode"], stdout=subprocess.PIPE)
        proc.wait()
    except KeyboardInterrupt:
        assert False, "Cannot proceed without root authority."


# Get the output from a terminal command and block any error messages from appearing.
def terminalCommand(command):
    output, _ = subprocess.Popen(["sudo"] + command.split(), stdout=subprocess.PIPE, stderr=DEVNULL).communicate()
    return output

# Run the program.
main()


