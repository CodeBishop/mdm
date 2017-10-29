#!/usr/bin/env python


import warnings

# Import pySMART but suppress the warning messages about not being root.
from pySMART import Device

# Attempt to load device smartctl info (and suppress pySmart warnings).
device = Device("/dev/sda")

print device.capacity
result = device.get_selftest_result()
