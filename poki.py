#!/usr/bin/env python


# TO DO
#   Add functionality to capture any errors that are reported in the column of dashes at the end of a smartctl -a output. For any item in that column that is NOT a dash then that whole line should be shown in the output.

import re
import subprocess
import os
import inspect
import sys

from pySMART import Device

# Fetch the null device for dumping unsightly error messages into.
DEVNULL = open(os.devnull, 'w')
MISSING_FIELD = ''  # This is what capture() returns if can't find the search string.
RECORD_CAPTURE_FAILURE, IGNORE_CAPTURE_FAILURE = 1, 2

captureFailures = list()
debugMode = False

# Program definition.
def main():
    # Hide traceback dump unless in debug mode.
    if not debugMode:
        sys.tracebacklimit = 0

    # Check for root.
    haltWithoutRootAuthority()

    # Load hard drive data.
    sda = Device("/dev/sda")
    print sda.serial
    print sda.all_attributes()
    print sda.model, sda.capacity
    print "Device name: ", sda.name
    print "Interface: ", sda.interface
    print "Is SSD:", sda.is_ssd
    print sda.all_selftests()

    # smartctlOutput = terminalCommand('smartctl -s on -a /dev/sda')
    # print smartctlOutput
    # print "Serial: " + capture(r"Serial Number:\w*(.*)", smartctlOutput, IGNORE_CAPTURE_FAILURE)


# Use a regular expression to capture part of a string or return MISSING_FIELD if unable.
def capture(pattern, text, failureAction=RECORD_CAPTURE_FAILURE):
    result = re.search(pattern, text)
    if result and result.group(1):
        return result.group(1)
    else:
        if failureAction == RECORD_CAPTURE_FAILURE:
            caller = inspect.stack()[1][3]
            captureFailures.append((caller, pattern, text))
        return MISSING_FIELD


# Output debugging information about any capture() calls that failed to find their target data.
def dumpCaptureFailures():
    for (caller, pattern, text) in captureFailures:
        # Eliminate excess whitespace and newlines from descriptions of searched text.
        text = re.sub(r"\s{2,}|\n", " ", text)
        # Concatenate excessively long searched text strings.
        if len(text) > 100:
            text = text[:100] + " ..."
        print "capture() failed to match: r\"" + pattern + "\""
        print "   in string: " + text
        print "   when called by: " + caller + "()" + "\n"


# Run no-op (:) with sudo and halt if lacking root authority.
def haltWithoutRootAuthority():
    try:
        proc = subprocess.Popen(["sudo", ":"], stdout=subprocess.PIPE)
        proc.wait()
    except KeyboardInterrupt:
        assert False, "Cannot proceed without root authority."


# Get the output from a terminal command and block any error messages from appearing.
def terminalCommand(command):
    output, _ = subprocess.Popen(["sudo"] + command.split(), stdout=subprocess.PIPE, stderr=DEVNULL).communicate()
    return output


# Remove junk words, irrelevant punctuation and multiple spaces from a field string.
# def sanitizeString(string):
#     # Remove junk words like "corporation", "ltd", etc
#     for word in junkWords:
#         string = re.sub('(?i)' + word, '', string)
#     # Fix words that can be written more neatly.
#     for badWord in correctableWords.keys():
#         goodWord = correctableWords[badWord]
#         string = re.sub('(?i)' + badWord, goodWord, string)
#     # Remove junk punctuation.
#     string = re.sub(',', '', string)
#     string = re.sub('\[', '', string)
#     string = re.sub('\]', '', string)
#     return stripExcessWhitespace(string)


# Reduce multiple whitespaces to a single space and eliminate leading and trailing whitespace.
def stripExcessWhitespace(string):
    # Reduce multiple whitespace sections to a single space.
    string = re.sub('\s\s+', ' ', string)
    # Remove leading and trailing whitespace.
    string = re.sub('^\s*', '', string)
    string = re.sub('\s*$', '', string)
    return string


# Run the program.
main()


