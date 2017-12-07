import os
import re
import subprocess
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
SMART_STATUS_CODE_NOT_INITIALIZED = -1
SMART_STATUS_CODE_NOT_INITIALIZED_MSG = "SMART status code not initialized."
SMART_STATUS_CODE_NOT_FOUND = -2
SMART_STATUS_CODE_NOT_FOUND_MSG = "SMART status code not found in smartctl output."
NUMBER_OF_SMARTCTL_STATE_CODES = 256

# Helper function constants.
SEARCH_FAILED = -1

# Smart test status codes.
SMART_CODE_IDLE = 0  # Drive is not smart testing.
SMART_CODE_INTERRUPTED = 32  # Drive is idle and most recent test was interrupted before completion.
SMART_CODE_INTERRUPTED2 = 33  # Drive is idle and most recent test was interrupted before completion.
SMART_CODE_ABORTED = 24  # Drive is idle and most recent test was aborted by user.
SMART_CODE_ABORTED2 = 25  # Drive is idle and most recent test was aborted by user.

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
        self.attributes = list()
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
        self.smartStatusCode = SMART_STATUS_CODE_NOT_INITIALIZED
        self.smartStatusDescription = SMART_STATUS_CODE_NOT_INITIALIZED_MSG
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
        command = "smartctl -s on -a " + self.devicePath
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

        # Search for SMART status code in smartctl output.
        smartStatusCodeSearch = capture(r"Self-test execution status:\s*\(\s*(\d+)\s*\)", self.smartctlOutput)

        # If smart status code wasn't found in smartctl output then.
        if smartStatusCodeSearch is "":
            self.smartStatusCode = SMART_STATUS_CODE_NOT_INITIALIZED
            self.smartStatusDescription = SMART_STATUS_CODE_NOT_FOUND_MSG
            # If smart status code is unavailable and drive is not being wiped then presume drive is idle.
            if self.state is not DR_STATE_WIPING:
                self.state = DR_STATE_IDLE
        # If SMART status code was found then record that status.
        else:
            self.smartStatusCode = int(smartStatusCodeSearch)
            # Determine device state based on whether smartctl reports a test-in-progress.
            if self.smartStatusCode in [SMART_CODE_IDLE, SMART_CODE_INTERRUPTED, SMART_CODE_INTERRUPTED2,
                                        SMART_CODE_ABORTED, SMART_CODE_ABORTED2]:
                self.state = DR_STATE_IDLE
            else:
                # If the type of test being run is not already known then just record it state unknown.
                if self.state not in [DR_STATE_SHORT_TESTING, DR_STATE_LONG_TESTING] and \
                                self.smartStatusCode not in range(241, 250):  # Range of SMART testing codes = 241-249.
                    self.state = DR_STATE_UNKNOWN
                # Otherwise record it as testing.
                else:
                    self.state = DR_STATE_TESTING
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

        # Look for drive size.
        self.capacity = capture(r"User Capacity:[\d,\w\s]*\[([\w\s]+)\]", self.smartctlOutput)

        # Search for a reallocated sector count entry from the SMART attributes list.
        line = capture(r"(Reallocated_Sector_Ct.*)", self.smartctlOutput)
        # If a reallocated sector count entry was found then extract the last number in that line.
        if line is not None:
            self.reallocCount = capture(r"(\d+)(?!.*\d)", line)

        # Look for self-test log.
        startOfTestHistory = firstMatchPosition("SMART Self-test log structure", self.smartctlOutput)
        if startOfTestHistory is not SEARCH_FAILED:
            linesFromTestLogStart = self.smartctlOutput[startOfTestHistory:].split('\n')
            self.testHistoryHeader = linesFromTestLogStart[1]  # Header is first line after search match.
            for line in linesFromTestLogStart:
                if len(line) > 0 and line[0] == '#':  # Test result lines start with a pound sign.
                    self.testHistory.append(line)

        # Look for attributes.
        smartAttrStartPos = firstMatchPosition(r"ID# ATTRIBUTE_NAME", self.smartctlOutput)
        # Get a string from start of attribute table onwards.
        remainingOutput = self.smartctlOutput[smartAttrStartPos:]
        while True:
            # Capture the next line.
            attributeString = capture(r"\n.*", remainingOutput)
            if attributeString == "":
                break
            else:
                self.attributes.append(attributeString)
                # Reduce the remaining text.
                remainingOutput = remainingOutput[len(attributeString):]

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

    def runLongTest(self):
        # Call smartctl directly to run a long test.
        rawResults = terminalCommand("smartctl -s on -t long " + self.devicePath)

    def abortTest(self):
        # Call smartctl directly to abort currently running test.
        rawResults = terminalCommand("smartctl -s on -X " + self.devicePath)

    def buildFailedAttributeList(self):
        for attribute in self.device.attributes:
            if attribute and attribute.when_failed != "-":
                self.failedAttributes.append(self.devicePath + " " + str(attribute))

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
