#!/usr/bin/env python

# Tinker - An improved version of poki using the ncurses library.
from pySMART.utils import admin
from storageDevice import *

import curses
import glob
import os
import time

# Drawing positions for view layout.
POS_BX = 1  # Left side of search/help bar.
POS_BY = 3  # Top side of search/help bar.
POS_DLX = 6  # Left side of drive list.
POS_DLY = 6  # Top side of drive list.

SELECTOR_ABSENT = -1
NO_KEYS_PRESSED = -1
ESCAPE_KEY = 27
RAPID_KEYPRESS_THRESHOLD = 30  # Minimum milliseconds between two getch() calls for input to be considered user-based.
SEARCH_PROMPT = "Find: "

# Before initializing curses, remove the Esc key delay from the OS environment.
os.environ.setdefault('ESCDELAY', '0')

# Check for root.
if not admin():
    print "Only user ID #0 (root) can run this program"
    exit(1)


def main(screen):
    screen.nodelay(True)  # Make getch() non-blocking.
    devices = list()
    selector = SELECTOR_ABSENT  # Hide the drive selector until drives are found.
    searchString = ""
    searchModeFlag = False

    exitFlag = False
    redrawScreen = True  # Signals that the program should redraw the screen.
    refreshDevices = True  # Signals that the program should rescan all the drives.
    while not exitFlag:
        # Rescan the drives if signaled to.
        if refreshDevices:
            # Reset the signal flag.
            refreshDevices = False
            # Rescan the drives
            devices = findAllDrives()
            # Reset the selector position.
            selector = 0 if len(devices) > 0 else SELECTOR_ABSENT

        # Draw the screen if anything has changed.
        if redrawScreen:
            # Reset the signal flag.
            redrawScreen = False

            # Clear the screen
            screen.clear()
            screen.border(0)

            # Draw the program title.
            screen.addstr(1, 1, "Drive Scanner")

            # Draw the search bar or help bar.
            if searchModeFlag:
                screen.addstr(POS_BY, POS_BX, SEARCH_PROMPT + searchString)
            else:
                screen.addstr(POS_BY, POS_BX, "(f)ind (q)uit")

            # Draw the drive list.
            screen.addstr(POS_DLY - 1, POS_DLX, summaryHeader())
            for y in range(len(devices)):
                screen.addstr(POS_DLY + y, POS_DLX, devices[y].oneLineSummary())

            # Draw the selector.
            if selector is not SELECTOR_ABSENT:
                screen.addstr(POS_DLY + selector, POS_DLX - 4, "-->")

            # Show the cursor when in search mode and hide it the rest of the time.
            if searchModeFlag:
                curses.curs_set(1)
                # Position the cursor by printing nothing where it should be.
                screen.addstr(POS_BY, POS_BX + len(SEARCH_PROMPT + searchString), "")

            # Hide the cursor when not in search mode.
            else:
                curses.curs_set(0)

            # Update the view.
            screen.refresh()

        # Check for and handle keypresses.
        keypress = screen.getch()
        if keypress is not NO_KEYS_PRESSED:
            # Assume the screen will need to be redrawn anytime a key is pressed.
            redrawScreen = True

            # In search mode most keys should be added to the search string until Esc or Enter are pressed.
            if searchModeFlag:
                if keypress == ESCAPE_KEY:
                    searchString = ""
                    searchModeFlag = False
                elif keypress == curses.KEY_BACKSPACE:
                    searchString = searchString[:-1]
                elif keypress < 256:  # ASCII keys get added to search.
                    searchString += curses.keyname(keypress)
                # All other keys are ignored in search mode.

            # When not in search mode, all keys are interpreted as commands.
            else:
                # Pause briefly to see if another keypress happens rapidly enough to imply barcode scanning.
                millisecondsElapsed = 0
                startTime = time.time()
                while millisecondsElapsed < RAPID_KEYPRESS_THRESHOLD:
                    # Repeatedly query getch().
                    keypress2 = screen.getch()
                    if keypress2 is not NO_KEYS_PRESSED:
                        searchModeFlag = True
                        searchString += curses.keyname(keypress)  # Add the first keypress to the search.
                        keypress = keypress2  # Pass the second keypress forward.
                        break
                    millisecondsElapsed = int((time.time() - startTime) * 1000)

                # If a drive list is present then check for cursor keys.
                if len(devices) > 0:
                    if keypress == curses.KEY_DOWN:
                        selector = (selector + 1) % len(devices)
                    if keypress == curses.KEY_UP:
                        selector = (selector - 1) % len(devices)
                else:
                    selector = SELECTOR_ABSENT

                if keypress == ord('f'):
                    searchModeFlag = True

                if keypress == ord('q'):
                    exitFlag = True

        time.sleep(0.01)  # Sleep for this many seconds to reduce CPU load.


def findAllDrives():
    # Get a list of all hard drive device paths.
    devicePaths = glob.glob('/dev/sd?')

    devices = list()

    # Load each device and print a summary of it.
    for devicePath in sorted(devicePaths):
        # Attempt to load device smartctl info (and suppress pySmart warnings).
        device = StorageDevice(devicePath)
        devices.append(device)

    return devices

curses.wrapper(main)

