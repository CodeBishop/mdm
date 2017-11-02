import re
import sys
import warnings


# Import pySMART but suppress the warning messages about not being root.
warnings.filterwarnings("ignore")
from pySMART import Device
from pySMART.utils import admin
warnings.filterwarnings("default")

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
        self.smartCapable = None

        self.load(devicePath)

    def load(self, devicePath):
        warnings.filterwarnings("ignore")
        device = Device(devicePath)
        warnings.filterwarnings("default")
        self.smartCapable = False if (device.name is None or device.interface is None) else False

        return DW_LOAD_SUCCESS if self.smartCapable else DW_LOAD_FAILED

    def refresh(self):
        outcome = self.load(self.devicePath)
        return outcome

    def oneLineSummary(self):
        pass


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
