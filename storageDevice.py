import os
import re
import subprocess
import sys
import warnings


# Import pySMART but suppress the warning messages about not being root.
warnings.filterwarnings("ignore")
from pySMART import Device
warnings.filterwarnings("default")

# Open the null device for dumping unwanted output into.
DEVNULL = open(os.devnull, 'w')

# Possible states of a device's history: all past tests were good, one or more were bad, drive has never run a
#   short or long test, drive has never run a long test (but short ones were all good), drive has no history
#   because it is not SMART test capable.
DR_HIST_GOOD, DR_HIST_BAD, DR_HIST_NEVER_TESTED, DR_HIST_NEVER_LONG_TESTED, DR_HIST_NOT_TESTABLE = range(5)

# Possible current states of a device: drive is idle, drive is running a test, drive completed a test (while
#   this program was running), drive is being wiped, drive wipe is complete, drive status could not be discovered
DR_STATUS_IDLE, DR_STATUS_TESTING, DR_STATUS_TEST_DONE, DR_STATUS_WIPING, DR_STATUS_WIPE_DONE, \
    DR_STATUS_UNKNOWN, DR_STATUS_QUERYING, DR_STATUS_QUERY_DONE = range(8)

# Class-related constants.
DR_LOAD_FAILED, DR_LOAD_SUCCESS = range(2)


# Define column widths for displaying drive summaries (doesn't include one-space separator).
CW_CONNECTOR = 4
CW_GSENSE = 5
CW_DRIVE_TYPE = 4
CW_HOURS = 6
CW_MODEL = 20
CW_PATH = 8
CW_REALLOC = 7
CW_SERIAL = 16
CW_CAPACITY = 8
CW_TESTING_STATE = 22
CW_WHEN_FAILED_STATUS = 10


class StorageDevice:
    def __init__(self, devicePath):
        # Declare the members of this class.
        self.capacity = ""  # Drive size in MB, GB or TB as a string.
        self.connector = ""
        self.device = None
        self.devicePath = devicePath
        self.driveType = ""  # SSD or HDD.
        self.failedAttributes = list()  # Strings, one per WHEN_FAIL attribute.
        self.GSenseCount = ""
        self.hours = 0
        self.smartCapable = None
        self.smartctlOutput = ""
        self.serial = ""
        self.model = ""
        self.name = devicePath  # Device is referred to by its path.
        self.smartctlProcess = None  # Separate process allows non-blocking call to smartctl.
        self.reallocCount = -1  # Marker value for uninitialized integer.
        self.testHistory = list()  # Strings, one per test result from SMART test history.
        self.testProgress = -1  # Marker value for uninitialized integer.
        self.status = DR_STATUS_UNKNOWN

        # Start a smartctl process so the device fields can be filled.
        self.initiateQuery()
        # self.load(devicePath)  # DEBUG: Old way of doing things by using PySmart.

    # Run a smartctl process to get latest device info.
    def initiateQuery(self):
        self.smartctlProcess = subprocess.Popen("smartctl -a /dev/sda".split(), stdout=subprocess.PIPE, stderr=DEVNULL)
        self.status = DR_STATUS_QUERYING

    # Test if a smartctl query-in-progress has completed.
    def queryIsDone(self):
        if self.status == DR_STATUS_QUERYING and self.smartctlProcess.poll() is not None:
            self.status = DR_STATUS_QUERY_DONE  # Prevents communicate() from ever being called twice.
            self.smartctlOutput, _ = self.smartctlProcess.communicate()
            self.interpretSmartctlOutput()
            return True
        else:
            return False

    # Interpret the current stored raw output of smartctl to fill device fields.
    def interpretSmartctlOutput(self):
        self.serial = capture(r"Serial Number:\s*(\w+)", self.smartctlOutput)
        self.model = capture(r"Device Model:\s*(\w+)", self.smartctlOutput)
        # self.serial = capture(r"Serial Number:\s*(\w+)", self.smartctlOutput)

        # Determine if a smartctl test is in progress.
        testStateCode = int(capture(r"Self-test execution status:\s*\(\s*(\d+)\s*\)", self.smartctlOutput))
        if testStateCode == 0:
            self.status = DR_STATUS_IDLE
        elif testStateCode == 249:
            self.status = DR_STATUS_TESTING
            self.testProgress = int(capture(r"(\d+)% of test remaining", self.smartctlOutput))
        else:
            self.status = DR_STATUS_UNKNOWN

    # DEBUG: Remove this method after initiateQuery() is finished (and pySmart removed).
    def load(self, devicePath):
        warnings.filterwarnings("ignore")
        self.device = Device(devicePath)
        warnings.filterwarnings("default")
        self.smartCapable = False if (self.device.name is None or self.device.interface is None) else True

        if self.smartCapable:
            # Fill various fields with smartctl info.
            self.buildFailedAttributeList()
            if self.device.tests is not None:
                for testResult in self.device.tests:
                    self.testHistory.append(str(testResult))
            if self.device.serial is not None:
                self.serial = str(self.device.serial)
            if self.device.model is not None:
                self.model = str(self.device.model)
            if self.device.name is not None:
                self.name = str(self.device.name)
            if self.device.interface is not None:
                self.connector = str(self.device.interface).upper()
                if self.connector == "SAT":
                    self.connector = "SATA"
            if self.device.attributes[5] is not None:
                self.reallocCount = int(self.device.attributes[5].raw)

            # Call smartctl directly to see if a test is in progress.
            rawResults = terminalCommand("smartctl -s on -c " + self.devicePath)
            if re.search("previous self-test", rawResults):
                self.status = DR_STATUS_IDLE
            elif re.search("% of test remaining", rawResults):
                self.status = DR_STATUS_TESTING
                self.testProgress = int(capture(r"(\d+)% of test remaining", rawResults))
            else:
                self.status = DR_STATUS_UNKNOWN

        return DR_LOAD_SUCCESS if self.smartCapable else DR_LOAD_FAILED

    def runShortTest(self):
        # Call smartctl directly to run a short test.
        rawResults = terminalCommand("smartctl -s on -t short " + self.devicePath)

    def buildFailedAttributeList(self):
        for attribute in self.device.attributes:
            if attribute and attribute.when_failed != "-":
                self.failedAttributes.append(self.devicePath + " " + str(attribute))

    def refresh(self):
        outcome = self.load(self.devicePath)
        return outcome

    # Test if a given string matches any device field as a substring.
    def matchSearchString(self, searchString):
        # Look for the given searchString in various fields.
        if re.search(searchString, self.serial, re.IGNORECASE) or \
                re.search(searchString, self.model, re.IGNORECASE) or \
                re.search(searchString, self.devicePath, re.IGNORECASE) or \
                re.search(searchString, self.oneLineSummary(), re.IGNORECASE) or \
                re.search(searchString, self.name, re.IGNORECASE):
            return True
        else:
            return False

    def oneLineSummary(self):
        # if self.status = not self.smartCapable:
        #     return self.devicePath + " does not respond to smartctl enquiries."

        # Make a color-coded string of the reallocated sector count.
        if self.reallocCount > 0:
            reallocText = leftColumn(str(self.reallocCount), CW_REALLOC)
        elif self.reallocCount < 0:
            reallocText = leftColumn("???", CW_REALLOC)
        else:
            reallocText = leftColumn(str(self.reallocCount), CW_REALLOC)

        # Note whether the device has any failed attributes.
        if self.hasFailedAttributes():
            whenFailedStatus = leftColumn("see below", CW_WHEN_FAILED_STATUS)
        else:
            whenFailedStatus = leftColumn("-", CW_WHEN_FAILED_STATUS)

        # Describe current testing status.
        if self.status == DR_STATUS_UNKNOWN:
            testingState = leftColumn("unknown", CW_TESTING_STATE)
        elif self.status == DR_STATUS_IDLE:
            testingState = leftColumn("idle", CW_TESTING_STATE)
        elif self.status == DR_STATUS_QUERYING:
            testingState = leftColumn("querying", CW_TESTING_STATE)
        elif self.status == DR_STATUS_TESTING:
            testingState = leftColumn(str(self.testProgress) + '%', CW_TESTING_STATE)
        else:
            # Since these codes are defined in this program this error should never happen...
            testingState = leftColumn("unknown code:" + str(self.status), CW_TESTING_STATE)

        # Construct one-line summary of drive.
        description = ""
        description += leftColumn(self.devicePath, CW_PATH)
        description += leftColumn(self.connector, CW_CONNECTOR)
        description += leftColumn(self.driveType, CW_DRIVE_TYPE)
        description += leftColumn(self.capacity, CW_CAPACITY)
        description += leftColumn(self.model, CW_MODEL)
        description += leftColumn(self.serial, CW_SERIAL)
        description += reallocText
        description += leftColumn(str(self.hours), CW_HOURS)
        description += leftColumn(str(self.GSenseCount), CW_GSENSE)
        description += whenFailedStatus
        description += testingState

        return description

    def hasFailedAttributes(self):
        return len(self.failedAttributes) > 0


#######################################
# Module functions and static methods #
#######################################
def summaryHeader():
    header = ""
    header += leftColumn("Path", CW_PATH)
    header += leftColumn("Conn", CW_CONNECTOR)
    header += leftColumn("Type", CW_DRIVE_TYPE)
    header += leftColumn("Size", CW_CAPACITY)
    header += leftColumn("Model", CW_MODEL)
    header += leftColumn("Serial", CW_SERIAL)
    header += leftColumn("ReAlloc", CW_REALLOC)
    header += leftColumn("Hours", CW_HOURS)
    header += leftColumn("GSen", CW_GSENSE)
    header += leftColumn("WHENFAIL", CW_WHEN_FAILED_STATUS)
    header += leftColumn("TestState", CW_TESTING_STATE)
    return header


def attributeHeader():
    # Print out any WHEN_FAILED attributes that were found.
    return "PATH     ID# ATTRIBUTE_NAME          VAL WST THR TYPE     UPDATED WHEN_FAILED RAW_VALUE"


def leftColumn(someString, width):
    # Strip ANSI codes before calculating string length.
    length = len(re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', someString))

    # Left justify string, truncate (with ellipsis) or pad with spaces to fill column width.
    if length <= width:
        # NOTE: str.ljust() mis-formats this under some circumstances so don't use it.
        return someString + ' ' * (width - length + 1)
    else:
        return someString[:width-3] + "... "
    # Non-ellipsis version.
    # return someString.ljust(width)[:width] + ' '


# Get the output from a terminal command and block any error messages from appearing.
def terminalCommand(command):
    output, _ = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=DEVNULL).communicate()
    return output


# Use a regular expression to capture part of a string or return MISSING_FIELD if unable.
def capture(pattern, text):
    result = re.search(pattern, text)
    if result and result.group(1):
        return result.group(1)
    else:
        return ""
