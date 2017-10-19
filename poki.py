#!/usr/bin/env python

# Poki is a program for fetching the most pertinent Smartctl information on all connected
# drives and presenting it in a summary that fits on one page.


# TO DO
#   Test with various drives including both SSD and HDD.
#   Delete the reallocated_sector_ct attribute from Device to test handling.
#   Figure out why text is not being colored on sysrescue version of Linux. Other programs color their text on it.
#   Decide how to display WHEN_FAILED attributes. Separate column headered section for each drive?
#   Clean up the drive list so that it's fixed column widths (Example: realloc= always in same spot).

import re
import subprocess
import os
import inspect
import sys
import glob
import warnings

from pySMART import Device

# Color codes for printing in color to the terminal.
# default color \033[00m
# red \033[91m   green \033[92m   yellow \033[93m   magenta \033[94m   purple \033[95m   cyan \033[96m   gray \033[97m
COLOR_DEFAULT = '\033[00m'
COLOR_RED = '\033[91m'
COLOR_YELLOW = '\033[93m'
COLOR_GREEN = '\033[92m'


# Fetch the null device for dumping unsightly error messages into.
DEVNULL = open(os.devnull, 'w')
MISSING_FIELD = ''  # This is what capture() returns if can't find the search string.
RECORD_CAPTURE_FAILURE, IGNORE_CAPTURE_FAILURE = 1, 2

captureFailures = list()
debugMode = False

# DEBUG: Test formatted printing methods.
#  {index:min_length}, {index:min_length}, ...
print("{:5} {:5} {:5}".format('Path', 'TestDescription'[0:6], '[SK  ASC  ASCQ]'))

exit(0) #DEBUG
# Program definition.
def main():
    devicePaths = glob.glob('/dev/sd?')
    for devicePath in sorted(devicePaths):
        # Example output line:
        #     sda, 120GB Kingston SSD, 1408 hours, realloc=0

        # Show device name.
        sys.stdout.write(devicePath + ' ')

        # Attempt to load device smartctl info (and suppress pySmart warnings).
        warnings.filterwarnings("ignore")
        device = Device(devicePath)
        warnings.filterwarnings("default")
        if device.name is None or device.interface is None:
            print "does not respond to smartctl enquiries."
            continue

        # Construct and print smartctl entry for device.
        description = device.capacity + ' '
        description += "SSD " if device.is_ssd else "HDD "
        description += device.model + ' '

        # Fetch the number of reallocated sectors if smartctl knows it.
        if device.attributes[5] != None:
            reallocCount = int(device.attributes[5].raw)
            if reallocCount > 0:
                textColor = COLOR_RED
            else:
                textColor = COLOR_GREEN
            description += textColor + "realloc=" + str(reallocCount) + ' ' + COLOR_DEFAULT
        else:
            description += "realloc=??? "

        # Fetch the number of G-Sense errors if smartctl knows it.
        GSenseCount = str(device.attributes[191].raw) if device.attributes[191] else "???"
        description += "g-sense=" + GSenseCount + ' '

        # Fetch the number of hours if smartctl gives it without scanning.
        if device.attributes[9] != None:
            hours = int(re.findall("\d+", device.attributes[9].raw)[0])
            if hours > 10000:
                textColor = COLOR_YELLOW
            else:
                textColor = COLOR_DEFAULT
            description += textColor + "hours=" + str(hours) + ' ' + COLOR_DEFAULT
        else:
            description += "hours=??? "

        print description

        # List all WHEN_FAILED attributes that were found.
        for attribute in device.attributes:
            if attribute and attribute.when_failed != "-":
                print COLOR_YELLOW + str(attribute) + COLOR_DEFAULT

    # Hide traceback dump unless in debug mode.
    if not debugMode:
        sys.tracebacklimit = 0

    # Check for root.
    haltWithoutRootAuthority()

    # Load hard drive data.
    sda = Device("/dev/sda")
    # print "All attributes\n--------------\n", sda.all_attributes(), "\n"
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


