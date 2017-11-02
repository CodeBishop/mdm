import warnings

# Import pySMART but suppress the warning messages about not being root.
warnings.filterwarnings("ignore")
from pySMART import Device
from pySMART.utils import admin
warnings.filterwarnings("default")

# DeviceWrapper-related constants.
DW_LOAD_FAILED, DW_LOAD_SUCCESS = range(2)


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
