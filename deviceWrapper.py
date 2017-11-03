import re
import sys
import warnings


# Import pySMART but suppress the warning messages about not being root.
warnings.filterwarnings("ignore")
from pySMART import Device
from pySMART.utils import admin
warnings.filterwarnings("default")

# ANSI color codes that are both bash (Ubuntu) and zsh compatible (sysrescue).
# Taken from:  https://en.wikipedia.org/wiki/ANSI_escape_code#3.2F4_bit
COLOR_DEFAULT = '\x1b[0m'
COLOR_RED = '\x1b[1;31m'
COLOR_YELLOW = '\x1b[1;33m'
COLOR_GREEN = '\x1b[1;32m'

# DeviceWrapper-related constants.
DW_LOAD_FAILED, DW_LOAD_SUCCESS = range(2)

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
            else:
                print self.devicePath + " has no reallocated sector count!!!"

        return DW_LOAD_SUCCESS if self.smartCapable else DW_LOAD_FAILED

    def buildFailedAttributeList(self):
        for attribute in self.device.attributes:
            if attribute and attribute.when_failed != "-":
                self.failedAttributes.append(self.devicePath + " " + str(attribute))

    def refresh(self):
        outcome = self.load(self.devicePath)
        return outcome

    def matchSearchString(self, searchString):
        # Look for the given searchString in various fields.
        if re.search(searchString, self.serial, re.IGNORECASE) or \
                re.search(searchString, self.model, re.IGNORECASE) or \
                re.search(searchString, self.name, re.IGNORECASE):
            return True
        else:
            return False

    def oneLineSummary(self):
        if not self.smartCapable:
            return self.devicePath + " does not respond to smartctl enquiries."

        # Make a color-coded string of the reallocated sector count.
        if self.reallocCount > 0:
            reallocText = COLOR_RED + str(self.reallocCount) + COLOR_DEFAULT
        elif self.reallocCount < 0:
            reallocText = COLOR_YELLOW + "???" + COLOR_DEFAULT
        else:
            reallocText = COLOR_GREEN + str(self.reallocCount) + COLOR_DEFAULT

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
            driveHours = textColor + str(hours) + ' ' + COLOR_DEFAULT
        else:
            driveHours = "???"

        # Note whether the device has any failed attributes.
        if self.hasFailedAttributes():
            whenFailedStatus = COLOR_YELLOW + "see below" + COLOR_DEFAULT
        else:
            whenFailedStatus = "-"

        # Assess the current testing status of the device.
        testResultCode = self.device.get_selftest_result()[0]
        if testResultCode == 0:
            testingState = COLOR_GREEN + "complete" + COLOR_DEFAULT
        elif testResultCode == 1:
            testingState = "in progress"
        elif testResultCode == 2:
            testingState = "idle"
        else:
            testingState = COLOR_YELLOW + "state:" + str(self.device.get_selftest_result()) + COLOR_DEFAULT

        # Construct one-line summary of drive.
        description = ""
        description += leftColumn(self.devicePath, CW_PATH)
        description += leftColumn(("SSD" if self.device.is_ssd else "HDD"), CW_HDD_TYPE)
        description += leftColumn(str(self.device.capacity), CW_SIZE)
        description += leftColumn(self.model, CW_MODEL)
        description += leftColumn(self.device.serial, CW_SERIAL)
        description += leftColumn(reallocText, CW_REALLOC)
        description += leftColumn(driveHours, CW_DRIVEHOURS)
        description += leftColumn(GSenseCount, CW_GSENSE)
        description += leftColumn(whenFailedStatus, CW_WHENFAILEDSTATUS)
        description += leftColumn(testingState, CW_TESTINGSTATE)

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
