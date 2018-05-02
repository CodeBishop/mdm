#!/usr/bin/env python

import os
import re
import subprocess
import warnings
import datetime

from Attribute import Attribute
from mdmSMART.utils import *

# Test result messages that are innocuous.
harmlessTestMessages = ["Aborted by host", "Completed without error", "Self-test routine in progress",
                        "Interrupted (host reset)"]

# Open the null device for dumping unwanted output into.
DEVNULL = open(os.devnull, 'w')

# Possible states of a device's history: all past tests were good, one or more were bad, drive has never run a
#   short or long test, drive has never run a long test (but short ones were all good), drive has no history
#   because it is not SMART test capable.
DR_HIST_GOOD, DR_HIST_BAD, DR_HIST_NEVER_TESTED, DR_HIST_NEVER_LONG_TESTED, DR_HIST_NOT_TESTABLE = range(5)

# Possible drive states of an instance of this class.
numberOfPossibleDriveStates = 5
DR_STATE_UNKNOWN, DR_STATE_IDLE, DR_STATE_QUERYING, DR_STATE_TESTING,\
    DR_STATE_WIPING = range(numberOfPossibleDriveStates)

# Status descriptions.
DR_STATE_MSG = [None] * numberOfPossibleDriveStates  # Create empty list of given size.
DR_STATE_MSG[DR_STATE_UNKNOWN] = "Unknown"
DR_STATE_MSG[DR_STATE_IDLE] = "Idle"
DR_STATE_MSG[DR_STATE_QUERYING] = "Querying"
DR_STATE_MSG[DR_STATE_TESTING] = "Testing"  # Drive is testing but type of test is unknown.
DR_STATE_MSG[DR_STATE_WIPING] = "Wiping"

# Class-related constants.
DR_LOAD_FAILED, DR_LOAD_SUCCESS = range(2)
NOT_INITIALIZED = -1
SMART_STATUS_CODE_NOT_INITIALIZED = -1
SMART_STATUS_CODE_NOT_INITIALIZED_MSG = "SMART status code not initialized."
SMART_STATUS_CODE_NOT_FOUND = -2
SMART_STATUS_CODE_NOT_FOUND_MSG = "SMART status code not found in smartctl output."
NUMBER_OF_SMARTCTL_STATE_CODES = 256

# Smart test status codes.
SMART_CODE_IDLE = [0, 1]  # Drive is not smart testing.
SMART_CODE_ABORTED = [16, 17, 23, 24, 25, 39, 40, 41]  # Drive is idle and most recent test was aborted by user.
SMART_CODE_INTERRUPTED = 32  # Drive is idle and most recent test was interrupted before completion.
SMART_CODE_INTERRUPTED2 = 33  # Drive is idle and most recent test was interrupted before completion.
SMART_CODE_READ_FAILURE = [112, 118]  # Drive failed most recent test with read failure.

# Attribute ID numbers.
ATTR_REALLOC = 5
ATTR_HOURS = 9
ATTR_GSENSE1 = 191
ATTR_GSENSE2 = 221

# Attributes that should always be shown (unnamed numbers are from attribute table in Wikipedia's SMART article).
IMPORTANT_ATTRIBUTES = [ATTR_REALLOC, ATTR_HOURS, ATTR_GSENSE1, ATTR_GSENSE2, 10, 184, 187, 188, 196, 197, 198, 201]


class Drive(object):
    def __init__(self, devicePath):
        # Declare the members of this class.
        self.attributes = [None] * 256  # Create list of unfilled attributes.
        self.capacity = ""  # Drive size in MB, GB or TB as a string.
        self.unknownUSBBridge = False
        self.device = None
        self.devicePath = devicePath
        self.estimatedCompletionTime = None
        self.GSenseCount = ""
        self.hours = NOT_INITIALIZED
        self.importantAttributes = list()  # Attributes that should always be shown (like WHEN_FAILs).
        self.lastTestAborted = False  # Drive has a test abortion in-progress.
        self.model = ""
        self.name = devicePath  # Device is referred to by its path.
        self.reallocCount = NOT_INITIALIZED  # Marker value for uninitialized integer.
        self.rotationRate = ""  # RPM (5400, 7200, ..) or SSD.
        self.serial = ""
        self.smartCapable = False  # Assume a drive is not SMART-capable until proven otherwise.
        self.smartctlOutput = ""  # All smartctl output as a single string.
        self.smartctlLines = list()  # All smartctl output as a list of strings, one per line.
        self.smartctlProcess = None  # Separate process allows non-blocking call to smartctl.
        self.smartStatusCode = SMART_STATUS_CODE_NOT_INITIALIZED
        self.smartStatusDescription = SMART_STATUS_CODE_NOT_INITIALIZED_MSG
        self.state = DR_STATE_UNKNOWN
        self.testHistory = list()  # Strings, one per test result from SMART test history.
        self.testHistoryHeader = ""  # Test history column header as given by smartctl.
        self.testPercentage = NOT_INITIALIZED  # Percentage completion of test.

        # Start a smartctl process so the device fields can be filled.
        self.initiateQuery()

    # Run a smartctl process to get latest device info.
    def initiateQuery(self):
        command = "smartctl -s on -a " + self.devicePath
        self.smartctlProcess = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=DEVNULL)
        self.state = DR_STATE_QUERYING

    # Test if a smartctl query-in-progress has completed.
    def queryIsDone(self):
        # If smartctl query terminal command has completed then update self based on terminal output.
        if self.state == DR_STATE_QUERYING:
            if self.smartctlProcess.poll() is not None:
                self.smartctlOutput, _ = self.smartctlProcess.communicate()
                self.smartctlLines = self.smartctlOutput.split('\n')
                self.interpretSmartctlOutput()
                return True  # Query has just completed.
            else:
                return False  # Querying but smartctl has not completed.
        else:
            return True  # Not querying.

    # Interpret the current stored raw output of smartctl to fill device fields.
    def interpretSmartctlOutput(self):
        if re.search("Unknown USB bridge", self.smartctlOutput):
            self.unknownUSBBridge = True
            self.smartCapable = False
            return  # Don't bother reading smartctl output if it's an unbridged USB device.
        else:
            self.smartCapable = True

        # Pull out the easy-to-capture values.
        self.serial = capture(r"Serial Number:\s*(.+)", self.smartctlOutput)
        self.model = capture(r"Device Model:\s*(.+)", self.smartctlOutput)

        # Determine the rotation rate or detect SSD.
        self.rotationRate = capture(r"Rotation Rate:\s*(\d+)", self.smartctlOutput)
        if self.rotationRate == CAPTURE_FAILED:
            if firstMatchPosition("Solid State Device", self.smartctlOutput) is not SEARCH_FAILED:
                self.rotationRate = "SSD"

        # Search for SMART status code in smartctl output.
        smartStatusCodeSearch = capture(r"Self-test execution status:\s*\(\s*(\d+)\s*\)", self.smartctlOutput)

        # If smart status code wasn't found in smartctl output then.
        if smartStatusCodeSearch is CAPTURE_FAILED:
            self.smartStatusCode = SMART_STATUS_CODE_NOT_INITIALIZED
            self.smartStatusDescription = SMART_STATUS_CODE_NOT_FOUND_MSG
            # If smart status code is unavailable and drive is not being wiped then presume drive is idle.
            if self.state is not DR_STATE_WIPING:
                self.state = DR_STATE_IDLE
        # If SMART status code was found then record that status.
        else:
            self.smartStatusCode = int(smartStatusCodeSearch)
            # Look for smartctl status codes that imply the drive is idle.
            if self.smartStatusCode in SMART_CODE_IDLE + [SMART_CODE_INTERRUPTED, SMART_CODE_INTERRUPTED2] + \
                    SMART_CODE_ABORTED:
                self.state = DR_STATE_IDLE
            # Look for smartctl status codes that imply the drive is running a test.
            elif self.smartStatusCode in range(241, 250):  # Range of SMART testing codes = 241-249.
                self.state = DR_STATE_TESTING
                completionPercentage = (250 - self.smartStatusCode) * 10
                self.testPercentage = completionPercentage
            # If smartctl status code is not recognized that specify the drive state as unknown.
            else:
                self.state = DR_STATE_UNKNOWN
            # Search for SMART status message in smartctl output.
            smartStatusDescSearch = capture(r"Self-test execution status:\s*\(\s*\d+\s*\)\s*(.*)", self.smartctlOutput)
            # If status description wasn't found then report that fact.
            if smartStatusDescSearch is "":
                self.smartStatusDescription = "SMART status description could not be found in smartctl output."
            # If status description was found then use it.
            else:
                # Capture status description and then look for subsequent lines if it's a multiline description.
                self.smartStatusDescription = smartStatusDescSearch
                # Find the start of the description line.
                smartStatusDescLineStartPos = firstMatchPosition(r"Self-test execution status:", self.smartctlOutput)
                # Get a string from start of description onwards.
                smartStatusLineOnwards = self.smartctlOutput[smartStatusDescLineStartPos:]
                while True:
                    # Find the end of the current description line.
                    smartStatusDescEndOfLine = firstMatchPosition(r"\n", smartStatusLineOnwards)
                    # Get a string from the end of the current line onwards.
                    smartStatusDescNextLineOnwards = smartStatusLineOnwards[smartStatusDescEndOfLine + 1:]
                    # Search for whitespace at start of next line (ie, indentation).
                    smartStatusDescNextLinePos = firstMatchPosition(r"^\s", smartStatusDescNextLineOnwards)
                    # If next line is indented.
                    if smartStatusDescNextLinePos is not SEARCH_FAILED:
                        # Capture the next line of multiline description and ensure appended line has a space.
                        smartStatusDescSearch = capture(r"\s*(.*)", smartStatusDescNextLineOnwards)
                        self.smartStatusDescription += " " + smartStatusDescSearch
                        # Remove any double-spaces introduced by spaces at end of lines and appended spaces.
                        self.smartStatusDescription = ' '.join(self.smartStatusDescription.split())
                        # Get a string from position in description onwards.
                        smartStatusLineOnwards = smartStatusDescNextLineOnwards[smartStatusDescNextLinePos:]
                    else:
                        break

        # If testing is not now occurring then ensure that test timing estimates are disabled.
        if self.state is not DR_STATE_TESTING:
            self.resetTestCompletion()

        # Look for drive size.
        self.capacity = capture(r"User Capacity:\s*.*\[(.*)\]", self.smartctlOutput)

        # Look for self-test log.
        startOfTestHistory = firstMatchPosition("SMART Self-test log structure", self.smartctlOutput)
        if startOfTestHistory is not SEARCH_FAILED:
            self.testHistory = list()  # Reset test history.
            linesFromTestLogStart = self.smartctlOutput[startOfTestHistory:].split('\n')
            self.testHistoryHeader = linesFromTestLogStart[1]  # Header is first line after search match.
            for line in linesFromTestLogStart:
                # For each test result (lines that start with a # sign).
                if len(line) > 0 and line[0] == '#':  # Test result lines start with a pound sign.
                    self.testHistory.append(line)

        # Get the drive attributes.
        self.importantAttributes = list()  # Reset attribute list.
        for i in range(len(self.smartctlLines)):
            # Look for the start of the attributes section.
            if self.smartctlLines[i] == "Vendor Specific SMART Attributes with Thresholds:":
                # Read in each line of the input.
                for j in range(i + 2, len(self.smartctlLines)):
                    if len(self.smartctlLines[j]) > 2:
                        # Build an Attribute object.
                        attribute = Attribute(self.smartctlLines[j])
                        self.attributes[attribute.idNumber] = attribute
                        # Add it to the list of important attributes if it's one that should always be shown.
                        if attribute.idNumber in IMPORTANT_ATTRIBUTES:
                            self.importantAttributes.append(attribute)
                        # Add it to the list of important attributes if it has a WHEN_FAIL entry.
                        elif not re.search(r"\w*-\w*", attribute.whenFailed):
                            self.importantAttributes.append(attribute)
                    else:
                        break

        # Extract particular data from the attributes if available.
        if self.attributes[5]:
            reallocString = capture(r"([0-9]+)", self.attributes[5].rawValue)
            if reallocString is not "":
                self.reallocCount = int(reallocString)
        if self.attributes[9]:
            hoursString = capture(r"([0-9]+)", self.attributes[9].rawValue)
            if hoursString is not "":
                self.hours = int(hoursString)
        if self.attributes[ATTR_GSENSE1]:
            self.GSenseCount = self.attributes[ATTR_GSENSE1].rawValue
        elif self.attributes[ATTR_GSENSE2]:
            self.GSenseCount = self.attributes[ATTR_GSENSE2].rawValue

    def runShortTest(self):
        self.runTest("smartctl -s on -t short " + self.devicePath)

    def runLongTest(self):
        self.runTest("smartctl -s on -t long " + self.devicePath)

    # Executes a given terminal command that should be a smartctl test.
    def runTest(self, command):
        if self.smartCapable and self.state not in [DR_STATE_TESTING, DR_STATE_WIPING]:
            terminalOutput = terminalCommand(command)
            eta = capture(r"Test will complete after (.*)", terminalOutput)
            if eta is not CAPTURE_FAILED:
                # Extract time and date substrings from smartctl output.
                #   Example: "Thu Mar 15 14:29:51 2018"
                self.estimatedCompletionTime = datetime.datetime.strptime(eta, "%a %b %d %H:%M:%S %Y")
            self.state = DR_STATE_TESTING
            self.initiateQuery()  # Call smartctl a 2nd time to confirm new status as testing.
            self.lastTestAborted = False

    def abortTest(self):
        # Call smartctl directly to abort currently running test.
        terminalCommand("smartctl -s on -X " + self.devicePath)
        self.resetTestCompletion()
        self.state = DR_STATE_UNKNOWN
        self.lastTestAborted = True

    def resetTestCompletion(self):
        self.estimatedCompletionTime = None
        self.testPercentage = NOT_INITIALIZED

    # Test if a given string matches any device field as a substring.
    def matchSearchString(self, searchString):
        # Look for the given searchString in various fields.
        if re.search(searchString, self.serial, re.IGNORECASE) or \
                re.search(searchString, self.model, re.IGNORECASE) or \
                re.search(searchString, self.devicePath, re.IGNORECASE) or \
                re.search(searchString, self.name, re.IGNORECASE):
            return True
        else:
            return False

    # Return the drive status description as a short string.
    def statusString(self):
        if self.state is DR_STATE_TESTING and 241 <= self.smartStatusCode <= 249:
            completion = (250 - self.smartStatusCode) * 10
            return DR_STATE_MSG[self.state] + " " + str(self.testPercentage) + "%"
        return DR_STATE_MSG[self.state]

    # If any attribute has something other than a dash for WHEN_FAIL then return True.
    def hasFailedAttributes(self):
        for attribute in self.attributes:
            if attribute and attribute.hasWhenFailed:
                return True
        return False

    # If any past test failed.
    def hasFailureHistory(self):
        for test in self.testHistory:
            if not any(msg in test for msg in harmlessTestMessages):
                return True
        return False

    # Return remaining test time (ETA) as string.
    def testTimeRemaining(self):
        # If an test completion time is known then calculate
        if self.estimatedCompletionTime:
            timeDelta = self.estimatedCompletionTime - datetime.datetime.now()
            hours, minutes = timeDelta.days * 24 + timeDelta.seconds // 3600, timeDelta.seconds // 60 % 60
            if hours is not 0:
                return str(hours) + "h " + str(minutes) + "m"
            elif minutes is not 0:
                return str(minutes) + "m"
            else:
                return str(timeDelta.seconds) + "s"
        else:
            return ""
