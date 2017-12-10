
class Attribute(object):
    def __init__(self, smartctlLine):
        self.smartctLine = smartctlLine

        # Fill the attribute values by interpreting the one line output from smartctl.
        self.idNumber = smartctlLine[0:3]
        self.name = smartctlLine[4:28]
        self.flag
        self.value
        self.worst
        self.threshold
        self.type
        self.updated
        self.whenFailed
        self.rawValue

