#!/usr/bin/env python

# A collection of utility functions and classes for MDM (Multi-Drive Manager)
import os
import re
import subprocess
import curses

# Open the null device for dumping unwanted output into.
DEVNULL = open(os.devnull, 'w')

# Utility function constants.
SEARCH_FAILED = -1
CAPTURE_FAILED = ""

CEC = "%%%"  # Escape code for colored or special text.
CECLEN = 1  # Number of chars after a color escape code.

CEC_RED = CEC + "1"
CEC_GREEN = CEC + "2"
CEC_YELLOW = CEC + "3"
CEC_BLUE = CEC + "4"
CEC_MAGENTA = CEC + "5"
CEC_CYAN = CEC + "6"
CEC_REVERSE = CEC + "r"

utilsWindow = None


def CECStringLength(text):
    return len(text) - text.count(CEC) * (len(CEC) + CECLEN)


def setPrintWindow(activeWindow):
    global utilsWindow
    utilsWindow = activeWindow


def setupCursesUtils(activeWindow):
    setPrintWindow(activeWindow)
    # Prepare color pairs.
    for i in range(1, 8):
        curses.init_pair(i, i, 0)


# If a CECString is longer than maxLength then cut it back and append ellipsis.
def cutToEllipsis(text, maxLength):
    if CECStringLength(text) > maxLength:
        ellipsis = ".."
        newText = ""
        newLength = 0
        i = 0
        while newLength < maxLength - len(ellipsis):
            # If next part of string is a CEC code then append it but don't count it.
            if text[i:i+len(CEC)] == CEC:
                newText += text[i:i+len(CEC) + CECLEN]
                i += len(CEC) + CECLEN
                print newText
            # Else it's a normal character and just append it.
            else:
                newText += text[i]
                i += 1
                newLength += 1
            print newText
            print str(newLength) + " < " + str(maxLength - len(ellipsis))
        # Return excess string with an ellipsis tacked on at the end.
        return newText + ellipsis
    # If the given string didn't exceed the max length then return it as-is.
    else:
        return text


def printAt(x, y, text, length=-1):
    # If string needs to fit a given length then cut it.
    if length > -1:
        text = cutToEllipsis(text, length)

    # Split the string by color-escape codes into a list of string portions.
    strings = text.split(CEC)

    # Draw first portion of string in plain color
    utilsWindow.addstr(y, x, strings[0], curses.A_BOLD)
    x += len(strings[0])

    # Reverse color flag.
    reverseFlag = 0
    colorCode = 0

    # Draw all subsequent string portions based on their first character (which should be their CEC value).
    for i in range(1, len(strings)):
        if len(strings[i]) >= CECLEN:
            colorCodeChar = strings[i][0:CECLEN]
            if colorCodeChar in "01234567":
                colorCode = curses.color_pair(int(colorCodeChar))
            elif colorCodeChar == 'r':
                if reverseFlag == 0:
                    reverseFlag = curses.A_REVERSE
                else:
                    reverseFlag = 0

            cursesCode = colorCode | curses.A_BOLD | reverseFlag
            utilsWindow.addstr(y, x, strings[i][1:], cursesCode)
        x += len(strings[i]) - CECLEN


def drawTable(table, columnWidths, left, top, width, height):
    for y in range(len(table)):
        i = 0
        for x in range(len(table[0])):
            printAt(left + i, top + y, table[y][x], columnWidths[x])
            i += columnWidths[x] + 1


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
        return CAPTURE_FAILED
