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

# Possible drive states of an instance of this class.
numberOfPossibleDriveStates = 7
DR_STATE_UNKNOWN, DR_STATE_IDLE, DR_STATE_QUERYING, DR_STATE_SHORT_TESTING, DR_STATE_LONG_TESTING, DR_STATE_TESTING,\
    DR_STATE_WIPING = range(numberOfPossibleDriveStates)
DR_STATE_MSG = [None] * numberOfPossibleDriveStates  # Create empty list of given size.
DR_STATE_MSG[DR_STATE_UNKNOWN] = "Unknown"
DR_STATE_MSG[DR_STATE_IDLE] = "Idle"
DR_STATE_MSG[DR_STATE_QUERYING] = "Querying"
DR_STATE_MSG[DR_STATE_SHORT_TESTING] = "Short testing"
DR_STATE_MSG[DR_STATE_LONG_TESTING] = "Long testing"
DR_STATE_MSG[DR_STATE_TESTING] = "Testing"  # Type of testing (short/long) is not known.
DR_STATE_MSG[DR_STATE_WIPING] = "Wiping"

# Class-related constants.
DR_LOAD_FAILED, DR_LOAD_SUCCESS = range(2)
NOT_INITIALIZED = -1
SMARTCTL_TEST_CODE_NOT_AVAILABLE = -1
SMARTCTL_TEST_STATE_MSG_NOT_AVAILABLE = "Smartctl has not reported a self-test execution status."

# Helper function constants.
SEARCH_FAILED = -1

# Smart test status codes.
SMART_IDLE = 0  # Drive is not smart testing.
SMART_INTERRUPTED = 33  # Drive is idle and most recent test was interrupted before completion.

# Define column widths for displaying drive summaries (doesn't include one-space separator).
CW_CONNECTOR = 4
CW_GSENSE = 5
CW_DRIVE_TYPE = 4
CW_HOURS = 6
CW_MODEL = 20
CW_PATH = 8
CW_REALLOC = 7
CW_SERIAL = 18
CW_CAPACITY = 8
CW_STATE = 15
CW_WHEN_FAILED_STATUS = 10


class StorageDevice:
    def __init__(self, devicePath):
        # Declare the members of this class.
        self.capacity = ""  # Drive size in MB, GB or TB as a string.
        self.connector = ""  # SATA, SCSI, USB, etc.
        self.device = None
        self.devicePath = devicePath
        self.driveType = ""  # SSD or HDD.
        self.failedAttributes = list()  # Strings, one per WHEN_FAIL attribute.
        self.GSenseCount = ""
        self.hours = 0
        self.model = ""
        self.name = devicePath  # Device is referred to by its path.
        self.reallocCount = -1  # Marker value for uninitialized integer.
        self.serial = ""
        self.smartCapable = None
        self.smartctlOutput = ""
        self.smartctlTestStateCode = SMARTCTL_TEST_CODE_NOT_AVAILABLE
        self.smartctlTestStateMsg = SMARTCTL_TEST_STATE_MSG_NOT_AVAILABLE
        self.state = DR_STATE_UNKNOWN
        self.smartctlProcess = None  # Separate process allows non-blocking call to smartctl.
        self.testHistory = list()  # Strings, one per test result from SMART test history.
        self.testHistoryHeader = ""  # Test history column header as given by smartctl.
        self.testProgress = NOT_INITIALIZED

        # Start a smartctl process so the device fields can be filled.
        self.initiateQuery()
        # self.load(devicePath)  # DEBUG: Old way of doing things by using PySmart.

    # Run a smartctl process to get latest device info.
    def initiateQuery(self):
        command = "smartctl -a " + self.devicePath
        self.smartctlProcess = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=DEVNULL)
        self.state = DR_STATE_QUERYING

    # Test if a smartctl query-in-progress has completed.
    def queryIsDone(self):
        if self.state == DR_STATE_QUERYING:
            if self.smartctlProcess.poll() is not None:
                self.smartctlOutput, _ = self.smartctlProcess.communicate()
                self.state = DR_STATE_UNKNOWN
                return True  # Query has just completed.
            else:
                return False  # Querying but smartctl has not completed.
        else:
            return True  # Not querying.

    # Interpret the current stored raw output of smartctl to fill device fields.
    def interpretSmartctlOutput(self):
        if re.search("Unknown USB bridge", self.smartctlOutput):
            self.connector = "USB"
            return  # Don't bother reading smartctl output if it's a USB device.

        self.serial = capture(r"Serial Number:\s*(\w+)", self.smartctlOutput)
        self.model = capture(r"Device Model:\s*(\w+)", self.smartctlOutput)

        testStateCodeString = capture(r"Self-test execution status:\s*\(\s*(\d+)\s*\)", self.smartctlOutput)

        # If smartctl reports test status then record that status.
        if testStateCodeString is not "":
            self.smartctlTestStateCode = int(testStateCodeString)
            # Determine device state based on whether smartctl reports a test-in-progress.
            if self.smartctlTestStateCode in [SMART_IDLE, SMART_INTERRUPTED]:
                self.state = DR_STATE_IDLE
            else:
                testStateMsg = capture(r"Self-test execution status:\s*\(\s*\d+\s*\)(.*)", self.smartctlOutput)
                self.smartctlTestStateMsg = testStateMsg
                # If the type of test being run is not already known then just record it as generic.
                if self.state not in [DR_STATE_SHORT_TESTING, DR_STATE_LONG_TESTING]:
                    self.state = DR_STATE_TESTING
        # If smartctl does not report test status then make a note of it.
        else:
            self.smartctlTestStateCode = SMARTCTL_TEST_CODE_NOT_AVAILABLE
            self.smartctlTestStateMsg = SMARTCTL_TEST_STATE_MSG_NOT_AVAILABLE
            # If the smartctl does not report testing and drive is not being wiped then presume the drive is idle.
            if self.state is not DR_STATE_WIPING:
                self.state = DR_STATE_IDLE

        # Look for self-test log.
        startOfTestHistory = firstMatchPosition("SMART Self-test log structure", self.smartctlOutput)
        if startOfTestHistory is not SEARCH_FAILED:
            linesFromTestLogStart = self.smartctlOutput[startOfTestHistory:].split('\n')
            self.testHistoryHeader = linesFromTestLogStart[1]  # Header is first line after search match.
            for line in linesFromTestLogStart:
                if len(line) > 0 and line[0] == '#':  # Test result lines start with a pound sign.
                    self.testHistory.append(line)


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
            # rawResults = terminalCommand("smartctl -s on -c " + self.devicePath)
            # if re.search("previous self-test", rawResults):
            #     self.status = DR_STATUS_IDLE
            # elif re.search("% of test remaining", rawResults):
            #     self.status = DR_STATUS_TESTING
            #     self.testProgress = int(capture(r"(\d+)% of test remaining", rawResults))
            # else:
            #     self.status = DR_STATUS_UNKNOWN

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
        description += leftColumn(DR_STATE_MSG[self.state], CW_STATE)

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
    header += leftColumn("State", CW_STATE)
    return header


def attributeHeader():
    # Print out any WHEN_FAILED attributes that were found.
    return "PATH     ID# ATTRIBUTE_NAME          VAL WST THR TYPE     UPDATED WHEN_FAILED RAW_VALUE"


def firstMatchPosition(searchString, text):
    searchResult = re.search(searchString, text)
    if searchResult is None:
        return SEARCH_FAILED
    else:
        return searchResult.start()


def leftColumn(someString, width):
    # Strip ANSI codes before calculating string length.
    length = len(re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', someString))

    # Left justify string, truncate (with ellipsis) or pad with spaces to fill column width.
    if length <= width:
        # NOTE: str.ljust() mis-formats this under some circumstances so don't use it.
        return someString + ' ' * (width - length + 1)
    else:
        return someString[:width-3] + "... "


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
