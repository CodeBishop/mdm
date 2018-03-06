#!/usr/bin/env python

# A collection of utility functions and classes for MDM (Multi-Drive Manager)
import os
import re
import subprocess
import curses

# Utility function constants.
# SEARCH_FAILED = -1

# Open the null device for dumping unwanted output into.
# DEVNULL = open(os.devnull, 'w')

CEC = "%%%"  # Escape code for colored or special text.
CECLEN = len(CEC) + 1  # Total length of an escape code.

utilsWindow = None


class ColoredString:
    def __init__(self, text):
        self.text = text

    def length(self):
        return len(self.text) - self.text.count(CEC) * CECLEN


def setPrintWindow(activeWindow):
    global utilsWindow
    utilsWindow = activeWindow


def setupCursesUtils(activeWindow):
    setPrintWindow(activeWindow)
    # Prepare color pairs.
    for i in range(0, 8):
        curses.init_pair(i + 1, i, 0)


def printAt(x, y, text):
    utilsWindow.addstr(x, y, text, curses.color_pair(color))
    # Split the string into a list of tuples of length, text and color/attribute)
    # Loop through the list printing.


# def firstMatchPosition(searchString, text):
#     searchResult = re.search(searchString, text)
#     if searchResult is None:
#         return SEARCH_FAILED
#     else:
#         return searchResult.start()
#
#
# def leftColumn(someString, width):
#     # Strip ANSI codes before calculating string length.
#     length = len(re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', someString))
#
#     # Left justify string, truncate (with ellipsis) or pad with spaces to fill column width.
#     if length <= width:
#         # NOTE: str.ljust() mis-formats this under some circumstances so don't use it.
#         return someString + ' ' * (width - length + 1)
#     else:
#         return someString[:width-3] + "... "
#
#
# # Get the output from a terminal command and block any error messages from appearing.
# def terminalCommand(command):
#     output, _ = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=DEVNULL).communicate()
#     return output
#
#
# # Use a regular expression to capture part of a string.
# def capture(pattern, text):
#     result = re.search(pattern, text, re.IGNORECASE)
#     if result and result.group:
#         return result.group(1)
#     else:
#         return ""
