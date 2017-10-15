#!/usr/bin/env python

# Poki is a program for fetching the most pertinent Smartctl information on all connected
# drives and presenting it in a summary that fits on one page.


# TO DO
#   Add functionality to capture any errors that are reported in the column of dashes at the end of a smartctl -a output. For any item in that column that is NOT a dash then that whole line should be shown in the output.
#   Test with various drives including both SSD and HDD.
#   Delete the reallocated_sector_ct attribute from Device to test handling.

import re
import subprocess
import os
import inspect
import sys
import glob

from pySMART import Device

# Fetch the null device for dumping unsightly error messages into.
DEVNULL = open(os.devnull, 'w')
MISSING_FIELD = ''  # This is what capture() returns if can't find the search string.
RECORD_CAPTURE_FAILURE, IGNORE_CAPTURE_FAILURE = 1, 2

captureFailures = list()
debugMode = False


# Program definition.
def main():
    devicePaths = glob.glob('/dev/sd?')
    for devicePath in devicePaths:
        # Example output line:
        #     sda, 120GB Kingston SSD, 1408 hours, realloc=0

        # Show device name.
        sys.stdout.write(devicePath[-3:] + ' ')

        # Attempt to load device smartctl info.
        device = Device(devicePath)

        # Construct and print smartctl entry for device.
        description = device.capacity + ' '
        description += "SSD " if device.is_ssd else "HDD "
        description += device.model + ' '
        description += "realloc=" + str(device.attributes[5].raw) + ' '
        print description

    # Hide traceback dump unless in debug mode.
    if not debugMode:
        sys.tracebacklimit = 0

    # Check for root.
    haltWithoutRootAuthority()

    # Load hard drive data.
    sda = Device("/dev/sda")
    print "All attributes\n--------------\n", sda.all_attributes(), "\n"
    print "All self tests\n--------------\n", sda.all_selftests(), "\n"
    print "Device model: ", sda.model
    print "Serial number: ", sda.serial
    print "Capacity: ", sda.capacity
    print "Device name: ", sda.name
    print "Interface: ", sda.interface
    print "Is SSD:", sda.is_ssd
    print "Assessment: ", sda.assessment
    print "Firmware: ", sda.firmware
    print "SMART suppored: ", sda.supports_smart


    # smartctlOutput = terminalCommand('smartctl -s on -a /dev/sda')
    # print smartctlOutput
    # print "Serial: " + capture(r"Serial Number:\w*(.*)", smartctlOutput, IGNORE_CAPTURE_FAILURE)


# def getAllDevices():

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


# Run "true" with sudo (which does nothing) to test for root authority.
def haltWithoutRootAuthority():
    try:
        proc = subprocess.Popen(["sudo", "true"], stdout=subprocess.PIPE)
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


