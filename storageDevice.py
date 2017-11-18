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

# ANSI color codes that are both bash (Ubuntu) and zsh compatible (sysrescue).
# Taken from:  https://en.wikipedia.org/wiki/ANSI_escape_code#3.2F4_bit
COLOR_RESET = '\x1b[0m'
COLOR_GREY = '\x1b[1;37m'
COLOR_RED = '\x1b[1;31m'
COLOR_YELLOW = '\x1b[1;33m'
COLOR_GREEN = '\x1b[1;32m'

MISSING_FIELD = "not found"  # This is what capture() returns if can't find the search string.

# Possible states of a device's history: all past tests were good, one or more were bad, drive has never run a
#   short or long test, drive has never run a long test (but short ones were all good), drive has no history
#   because it is not SMART test capable.
DR_HIST_GOOD, DR_HIST_BAD, DR_HIST_NEVER_TESTED, DR_HIST_NEVER_LONG_TESTED, DR_HIST_NOT_TESTABLE = range(5)

# Possible current states of a device: drive is idle, drive is running a test, drive completed a test (while
#   this program was running), drive is being wiped, drive wipe is complete, drive status could not be discovered
DR_STATUS_IDLE, DR_STATUS_TESTING, DR_STATUS_TEST_DONE, DR_STATUS_WIPING, DR_STATUS_WIPE_DONE, \
    DR_STATUS_UNKNOWN = range(6)

# Class-related constants.
DW_LOAD_FAILED, DW_LOAD_SUCCESS = range(2)


# Define column widths for displaying drive summaries (doesn't include one-space separator).
CW_CONNECTOR = 4
CW_DRIVE_HOURS = 7
CW_GSENSE = 5
CW_HDD_TYPE = 4
CW_MODEL = 20
CW_PATH = 8
CW_REALLOC = 7
CW_SERIAL = 16
CW_SIZE = 8
CW_TESTING_STATE = 22
CW_WHEN_FAILED_STATUS = 10


class StorageDevice:
    def __init__(self, devicePath):
        # Declare the members of this class.
        self.connector = ""
        self.device = None
        self.devicePath = devicePath
        self.failedAttributes = list()
        self.smartCapable = None
        self.serial = ""
        self.model = ""
        self.name = ""
        self.reallocCount = -1  # Marker value for uninitialized integer.
        self.testProgress = -1  # Marker value for uninitialized integer.
        self.status = DR_STATUS_UNKNOWN

        self.load(devicePath)

    def load(self, devicePath):
        warnings.filterwarnings("ignore")
        self.device = Device(devicePath)
        warnings.filterwarnings("default")
        self.smartCapable = False if (self.device.name is None or self.device.interface is None) else True

        if self.smartCapable:
            # Fill various fields with smartctl info.
            self.buildFailedAttributeList()
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

        return DW_LOAD_SUCCESS if self.smartCapable else DW_LOAD_FAILED

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
        if not self.smartCapable:
            return self.devicePath + " does not respond to smartctl enquiries."

        # Make a color-coded string of the reallocated sector count.
        if self.reallocCount > 0:
            reallocText = COLOR_RED + leftColumn(str(self.reallocCount), CW_REALLOC) + COLOR_GREY
        elif self.reallocCount < 0:
            reallocText = COLOR_YELLOW + leftColumn("???", CW_REALLOC) + COLOR_GREY
        else:
            reallocText = COLOR_GREEN + leftColumn(str(self.reallocCount), CW_REALLOC) + COLOR_GREY

        # Fetch the number of G-Sense errors if smartctl knows it.
        GSenseCount = str(self.device.attributes[191].raw) if self.device.attributes[191] else "???"

        # Fetch the number of hours if smartctl knows it.
        # NOTE: smartctl may output hour-count in scan results yet not have it as an "attribute".
        if self.device.attributes[9] is not None:
            hours = int(re.findall("\d+", self.device.attributes[9].raw)[0])
            if hours > 10000:
                textColor = COLOR_YELLOW
            else:
                textColor = COLOR_GREEN
            driveHours = textColor + leftColumn(str(hours), CW_DRIVE_HOURS) + COLOR_GREY
        else:
            driveHours = leftColumn("???", CW_DRIVE_HOURS)

        # Note whether the device has any failed attributes.
        if self.hasFailedAttributes():
            whenFailedStatus = COLOR_YELLOW + leftColumn("see below", CW_WHEN_FAILED_STATUS) + COLOR_GREY
        else:
            whenFailedStatus = COLOR_GREEN + leftColumn("-", CW_WHEN_FAILED_STATUS) + COLOR_GREY

        # Describe current testing status.
        if self.status == DR_STATUS_UNKNOWN:
            testingState = leftColumn("unknown", CW_TESTING_STATE)
        elif self.status == DR_STATUS_IDLE:
            testingState = leftColumn("idle", CW_TESTING_STATE)
        elif self.status == DR_STATUS_TESTING:
            testingState = COLOR_YELLOW + leftColumn(str(self.testProgress) + '%', CW_TESTING_STATE) + COLOR_GREY
        else:
            # Since these codes are defined in this program this error should never happen...
            testingState = COLOR_RED + leftColumn("unknown code:" + str(self.status), CW_TESTING_STATE) + COLOR_GREY

        # Construct one-line summary of drive.
        description = ""
        description += leftColumn(self.devicePath, CW_PATH)
        description += leftColumn(self.connector, CW_CONNECTOR)
        description += leftColumn(("SSD" if self.device.is_ssd else "HDD"), CW_HDD_TYPE)
        description += leftColumn(str(self.device.capacity), CW_SIZE)
        description += leftColumn(self.model, CW_MODEL)
        description += leftColumn(self.device.serial, CW_SERIAL)
        description += reallocText
        description += driveHours
        description += leftColumn(GSenseCount, CW_GSENSE)
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
    header += leftColumn("Type", CW_HDD_TYPE)
    header += leftColumn("Size", CW_SIZE)
    header += leftColumn("Model", CW_MODEL)
    header += leftColumn("Serial", CW_SERIAL)
    header += leftColumn("ReAlloc", CW_REALLOC)
    header += leftColumn("Hours", CW_DRIVE_HOURS)
    header += leftColumn("GSen", CW_GSENSE)
    header += leftColumn("WHENFAIL", CW_WHEN_FAILED_STATUS)
    header += leftColumn("TestState", CW_TESTING_STATE)
    return header


def attributeHeader():
    # Print out any WHEN_FAILED attributes that were found.
    return "\nPATH     ID# ATTRIBUTE_NAME          VAL WST THR TYPE     UPDATED WHEN_FAILED RAW_VALUE" +\
           "\n-----------------------------------------------------------------------------------------"


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
        return MISSING_FIELD
