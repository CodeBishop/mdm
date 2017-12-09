
class Attribute(object):
    def __init__(self, smartctlLine):
        self.smartctLine = smartctlLine

        # Fill the attribute values by interpreting the smartctlLine



        self.num = num
        """**(str):** Attribute's ID as a decimal value (1-255)."""
        self.name = name
        """
        **(str):** Attribute's name, as reported by smartmontools' drive.db.
        """
        self.flags = flags
        """**(str):** Attribute flags as a hexadecimal value (ie: 0x0032)."""
        self.value = value
        """**(str):** Attribute's current normalized value."""
        self.worst = worst
        """**(str):** Worst recorded normalized value for this attribute."""
        self.thresh = thresh
        """**(str):** Attribute's failure threshold."""
        self.type = attr_type
        """**(str):** Attribute's type, generally 'pre-fail' or 'old-age'."""
        self.updated = updated
        """
        **(str):** When is this attribute updated? Generally 'Always' or
        'Offline'
        """
        self.when_failed = when_failed
        """
        **(str):** When did this attribute cross below
        `pySMART.attribute.Attribute.thresh`? Reads '-' when not failed.
        Generally either 'FAILING_NOW' or 'In_the_Past' otherwise.
        """
        self.raw = raw
        """**(str):** Attribute's current raw (non-normalized) value."""
