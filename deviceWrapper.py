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
COLOR_DEFAULT = '\x1b[0m'
COLOR_RED = '\x1b[1;31m'
COLOR_YELLOW = '\x1b[1;33m'
COLOR_GREEN = '\x1b[1;32m'

# DeviceWrapper-related constants.
DW_LOAD_FAILED, DW_LOAD_SUCCESS = range(2)
DW_STATUS_IDLE, DW_STATUS_TEST_IN_PROGRESS = range(2)

MISSING_FIELD = "not found"  # This is what capture() returns if can't find the search string.

# Define column widths for displaying drive summaries (doesn't include one-space separator).
CW_DRIVEHOURS = 7
CW_GSENSE = 5
CW_HDD_TYPE = 4
CW_MODEL = 20
CW_PATH = 8
CW_REALLOC = 7
CW_SERIAL = 16
CW_SIZE = 8
CW_TESTINGSTATE = 11
CW_WHENFAILEDSTATUS = 9


class DeviceWrapper:
    def __init__(self, devicePath):
        # Declare members of the DeviceWrapper class.
        self.device = None
        self.devicePath = devicePath
        self.failedAttributes = list()
        self.smartCapable = None
        self.serial = ""
        self.model = ""
        self.name = ""
        self.reallocCount = -1  # Marker value for uninitialized integer.
        self.testProgress = -1  # Marker value for uninitialized integer.
        self.status = "unknown"

        self.load(devicePath)

    def load(self, devicePath):
        warnings.filterwarnings("ignore")
        self.device = Device(devicePath)
        warnings.filterwarnings("default")
        self.smartCapable = False if (self.device.name is None or self.device.interface is None) else True

        if self.smartCapable:
            # Fill various DeviceWrapper fields with smartctl info.
            self.buildFailedAttributeList()
            if self.device.serial is not None:
                self.serial = str(self.device.serial)
            if self.device.model is not None:
                self.model = str(self.device.model)
            if self.device.name is not None:
                self.name = str(self.device.name)
            if self.device.attributes[5] is not None:
                self.reallocCount = int(self.device.attributes[5].raw)

            # Call smartctl directly to see if a test is in progress.
            rawResults = terminalCommand("smartctl -s on -c " + self.devicePath)
            if re.search("previous self-test", rawResults):
                self.status = DW_STATUS_IDLE
            elif re.search("% of test remaining", rawResults):
                self.status = DW_STATUS_TEST_IN_PROGRESS
                self.testProgress = int(capture(r"(\d+)% of test remaining", rawResults))

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
                re.search(searchString, self.name, re.IGNORECASE):
            return True
        else:
            return False

    def oneLineSummary(self):
        if not self.smartCapable:
            return self.devicePath + " does not respond to smartctl enquiries."

        # Make a color-coded string of the reallocated sector count.
        if self.reallocCount > 0:
            reallocText = COLOR_RED + leftColumn(str(self.reallocCount), CW_REALLOC) + COLOR_DEFAULT
        elif self.reallocCount < 0:
            reallocText = COLOR_YELLOW + leftColumn("???", CW_REALLOC) + COLOR_DEFAULT
        else:
            reallocText = COLOR_GREEN + leftColumn(str(self.reallocCount), CW_REALLOC) + COLOR_DEFAULT

        # Fetch the number of G-Sense errors if smartctl knows it.
        GSenseCount = str(self.device.attributes[191].raw) if self.device.attributes[191] else "???"

        # Fetch the number of hours if smartctl knows it.
        # NOTE: smartctl may output hour-count in scan results yet not have it as an "attribute".
        if self.device.attributes[9] is not None:
            hours = int(re.findall("\d+", self.device.attributes[9].raw)[0])
            if hours > 10000:
                textColor = COLOR_YELLOW
            else:
                textColor = COLOR_DEFAULT
            driveHours = textColor + leftColumn(str(hours), CW_DRIVEHOURS) + ' ' + COLOR_DEFAULT
        else:
            driveHours = leftColumn("???", CW_DRIVEHOURS)

        # Note whether the device has any failed attributes.
        if self.hasFailedAttributes():
            whenFailedStatus = COLOR_YELLOW + leftColumn("see below", CW_WHENFAILEDSTATUS) + COLOR_DEFAULT
        else:
            whenFailedStatus = leftColumn("-", CW_WHENFAILEDSTATUS)

        # Describe current testing status.
        if self.status == DW_STATUS_IDLE:
            testingState = leftColumn("idle", CW_TESTINGSTATE)
        elif self.status == DW_STATUS_TEST_IN_PROGRESS:
            testingState = COLOR_YELLOW + leftColumn(str(self.testProgress), CW_TESTINGSTATE) + "%" + COLOR_DEFAULT
        else:
            testingState = COLOR_RED + leftColumn("Unrecognized status code", CW_TESTINGSTATE) + COLOR_DEFAULT

        # Construct one-line summary of drive.
        description = ""
        description += leftColumn(self.devicePath, CW_PATH)
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
    sys.stdout.write(leftColumn("Path", CW_PATH))
    sys.stdout.write(leftColumn("Type", CW_HDD_TYPE))
    sys.stdout.write(leftColumn("Size", CW_SIZE))
    sys.stdout.write(leftColumn("Model", CW_MODEL))
    sys.stdout.write(leftColumn("Serial", CW_SERIAL))
    sys.stdout.write(leftColumn("ReAlloc", CW_REALLOC))
    sys.stdout.write(leftColumn("Hours", CW_DRIVEHOURS))
    sys.stdout.write(leftColumn("GSen", CW_GSENSE))
    sys.stdout.write(leftColumn("WHENFAIL", CW_WHENFAILEDSTATUS))
    sys.stdout.write(leftColumn("TestState", CW_TESTINGSTATE))
    return "\n" + "-" * (CW_PATH + 1 + CW_HDD_TYPE + 1 + CW_SIZE + 1 + CW_MODEL + 1 +
                        CW_SERIAL + 1 + CW_REALLOC + 1 + CW_DRIVEHOURS + 1 +
                        CW_GSENSE + 1 + CW_WHENFAILEDSTATUS + 1 + CW_TESTINGSTATE)


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
