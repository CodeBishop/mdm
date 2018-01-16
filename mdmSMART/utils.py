#!/usr/bin/env python

# A collection of utility functions for MDM (Multi-Drive Manager)
import os
import re
import subprocess

# Utility function constants.
SEARCH_FAILED = -1

# Open the null device for dumping unwanted output into.
DEVNULL = open(os.devnull, 'w')


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
