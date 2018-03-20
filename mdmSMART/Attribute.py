#!/usr/bin/env python
import re


class Attribute(object):
    def __init__(self, smartctlLine):
        self.smartctlLine = smartctlLine

        # Fill the attribute values by interpreting the one line output from smartctl.
        self.idNumber = int(smartctlLine[0:3])
        self.name = smartctlLine[4:28]
        self.flag = smartctlLine[28:36]
        self.value = smartctlLine[37:43]
        self.worst = smartctlLine[43:49]
        self.threshold = smartctlLine[49:56]
        self.type = smartctlLine[56:66]
        self.updated = smartctlLine[66:75]
        self.whenFailed = smartctlLine[75:87]
        self.rawValue = smartctlLine[87:]
        self.hasWhenFailed = re.search(r"\w*-\w*", self.whenFailed) is None

