#!/usr/bin/env python

# A collection of utility functions and classes for MDM (Multi-Drive Manager)
import os
import re
import subprocess
import curses

# Utility function constants.
SEARCH_FAILED = -1

CEC = "%%%"  # Escape code for colored or special text.
CECLEN = 1  # Number of chars after a color escape code.

utilsWindow = None


def CECStringLength(text):
    return len(text) - text.count(CEC) * (len(CEC) + CECLEN)


def setPrintWindow(activeWindow):
    global utilsWindow
    utilsWindow = activeWindow


def setupCursesUtils(activeWindow):
    setPrintWindow(activeWindow)
    # Prepare color pairs.
    for i in range(0, 8):
        curses.init_pair(i + 1, i, 0)


def printAt(x, y, text):
    # Split the string into a list of tuples of length, text and color/attribute)
    strings = text.split(CEC)

    # Lay down first portion of string in plain color
    utilsWindow.addstr(y, x, strings[0], curses.A_BOLD)
    x += len(strings[0])

    # Lay down all subsequent strings based on their first character (which should be their CEC value).
    for i in range(1, len(strings)):
        if len(strings[i]) >= CECLEN:
            colorCode = strings[i][0:CECLEN]
            cursesCode = curses.color_pair(int(colorCode)) | curses.A_BOLD
            utilsWindow.addstr(y, x, strings[i][1:], cursesCode)
        x += len(strings[i]) - CECLEN


def firstMatchPosition(searchString, text):
    searchResult = re.search(searchString, text)
    if searchResult is None:
        return SEARCH_FAILED
    else:
        return searchResult.start()


def leftColumn(someString, width):
    # Strip ANSI codes before calculating string length.
    length = len(re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', someString))

    # Left justify string, truncate (with ellipsis) or pad with spaces to fill column width.
    if length <= width:
        # NOTE: str.ljust() mis-formats this under some circumstances so don't use it.
        return someString + ' ' * (width - length + 1)
    else:
        return someString[:width-3] + "... "


# Get the output from a terminal command and block any error messages from appearing.
def terminalCommand(command):
    output, _ = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=DEVNULL).communicate()
    return output


# Use a regular expression to capture part of a string.
def capture(pattern, text):
    result = re.search(pattern, text, re.IGNORECASE)
    if result and result.group:
        return result.group(1)
    else:
        return ""
