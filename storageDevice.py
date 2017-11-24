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
DR_LOAD_FAILED, DR_LOAD_SUCCESS = range(2)


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
        self.failedAttributes = list()  # Strings, one per WHEN_FAIL attribute.
        self.smartCapable = None
        self.serial = ""
        self.model = ""
        self.name = ""
        self.smartctlProcess = None  # Separate process allows non-blocking call to smartctl.
        self.reallocCount = -1  # Marker value for uninitialized integer.
        self.testHistory = list()  # Strings, one per test result from SMART test history.
        self.testProgress = -1  # Marker value for uninitialized integer.
        self.status = DR_STATUS_UNKNOWN

        self.load(devicePath)

    def load2(self, devicePath):
        name = devicePath
        interface = None
        # """Instantiates and initializes the `pySMART.device.Device`."""
        # assert interface is None or interface.lower() in [
        #     'ata', 'csmi', 'sas', 'sat', 'sata', 'scsi']
        name = name.replace('/dev/', '')
        """
        **(str):** Device's hardware ID, without the '/dev/' prefix.
        (ie: sda (Linux), pd0 (Windows))
        """
        if name[:2].lower() == 'pd':
            name = pd_to_sd(name[2:])
        model = None
        """**(str):** Device's model number."""
        serial = None
        """**(str):** Device's serial number."""
        interface = interface
        """
        **(str):** Device's interface type. Must be one of:
            * **ATA** - Advanced Technology Attachment
            * **SATA** - Serial ATA
            * **SCSI** - Small Computer Systems Interface
            * **SAS** - Serial Attached SCSI
            * **SAT** - SCSI-to-ATA Translation (SATA device plugged into a
            SAS port)
            * **CSMI** - Common Storage Management Interface (Intel ICH /
            Matrix RAID)
        Generally this should not be specified to allow auto-detection to occur.
        Otherwise, this value overrides the auto-detected type and could
        produce unexpected or no data.
        """
        capacity = None
        """**(str):** Device's user capacity."""
        firmware = None
        """**(str):** Device's firmware version."""
        supports_smart = False
        """
        **(bool):** True if the device supports SMART (or SCSI equivalent) and
        has the feature set enabled. False otherwise.
        """
        assessment = None
        """**(str):** SMART health self-assessment as reported by the device."""
        messages = []
        """
        **(list of str):** Contains any SMART warnings or other error messages
        reported by the device (ie: ASCQ codes).
        """
        is_ssd = None
        """
        **(bool):** True if this device is a Solid State Drive.
        False otherwise.
        """
        attributes = [None] * 256
        """
        **(list of `Attribute`):** Contains the complete SMART table information
        for this device, as provided by smartctl. Indexed by attribute #,
        values are set to 'None' for attributes not suported by this device.
        """
        tests = []
        """
        **(list of `Log_Entry`):** Contains the complete SMART self-test log
        for this device, as provided by smartctl. If no SMART self-tests have
        been recorded, contains a `None` type instead.
        """
        _test_running = False
        """
        **(bool):** True if a self-test is currently being run. False otherwise.
        """
        _test_ECD = None
        """
        **(str):** Estimated completion time of the running SMART selftest.
        Not provided by SAS/SCSI devices.
        """
        diags = {}
        """
        **(dict of str):** Contains parsed and processed diagnostic information
        extracted from the SMART information. Currently only populated for
        SAS and SCSI devices, since ATA/SATA SMART attributes are manufacturer
        proprietary.
        """
        if name is None:
            warnings.warn("\nDevice '{0}' does not exist! "
                          "This object should be destroyed.".format(name))
            return
        # If no interface type was provided, scan for the device
        elif interface is None:
            _grep = 'find' if OS == 'Windows' else 'grep'
            cmd = Popen('smartctl --scan-open | {0} "{1}"'.format(
                _grep, name), shell=True, stdout=PIPE, stderr=PIPE)
            _stdout, _stderr = cmd.communicate()
            if _stdout != '':
                interface = _stdout.split(' ')[2]
                # Disambiguate the generic interface to a specific type
                _classify()
            else:
                warnings.warn("\nDevice '{0}' does not exist! "
                              "This object should be destroyed.".format(name))
                return
        # If a valid device was detected, populate its information
        if interface is not None:
            update()

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
        if not self.smartCapable:
            return self.devicePath + " does not respond to smartctl enquiries."

        # Make a color-coded string of the reallocated sector count.
        if self.reallocCount > 0:
            reallocText = leftColumn(str(self.reallocCount), CW_REALLOC)
        elif self.reallocCount < 0:
            reallocText = leftColumn("???", CW_REALLOC)
        else:
            reallocText = leftColumn(str(self.reallocCount), CW_REALLOC)

        # Fetch the number of G-Sense errors if smartctl knows it.
        GSenseCount = str(self.device.attributes[191].raw) if self.device.attributes[191] else "???"

        # Fetch the number of hours if smartctl knows it.
        # NOTE: smartctl may output hour-count in scan results yet not have it as an "attribute".
        if self.device.attributes[9] is not None:
            hours = int(re.findall("\d+", self.device.attributes[9].raw)[0])
            driveHours = leftColumn(str(hours), CW_DRIVE_HOURS)
        else:
            driveHours = leftColumn("???", CW_DRIVE_HOURS)

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
        elif self.status == DR_STATUS_TESTING:
            testingState = leftColumn(str(self.testProgress) + '%', CW_TESTING_STATE)
        else:
            # Since these codes are defined in this program this error should never happen...
            testingState = leftColumn("unknown code:" + str(self.status), CW_TESTING_STATE)

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
        return MISSING_FIELD
