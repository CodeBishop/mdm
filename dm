#!/usr/bin/env python

# Welcome to dm, aka Drive Monkey.
# An improved version of poki using the ncurses library.

# Misc Notes
# Summary of sysrescue display differences.
#   The terminal does not get restored when a curses program ends. The prompt re-appears at the bottom
#       and the screen remains cluttered with whatever was on display.
#   Only 8 colors are available and the curses.COLORS constant reflects that fact.
#   Font effects: dim=underline=normal, reverse=standout(fg/bg color reversal), bold is brighter text.
#       blink is grey text on dark grey background (no blinking).

# To Do:
# Figure out why running on sysrescue isn't returning values for smartctl queries on the first pass.
# Clear the screen after the program exits so that it's obvious the program has ended. Restoring the terminal
#   on a sysrescue machine seems unlikely since Nano doesn't pull it off.


from pySMART.utils import admin
from storageDevice import *

import curses
import glob
import os
import time

# Drawing positions for view layout.
POS_BX = 1  # Left side of search/help bar.
POS_BY = 3  # Top side of search/help bar.
POS_MX = 1  # Left side of message bar.
POS_MY = 5  # Top side of message bar.
POS_DLX = 8  # Left side of drive list.
POS_DLY = 8  # Top side of drive list.

SELECTOR_ABSENT = -1
NO_KEYS_PRESSED = -1
ESCAPE_KEY = 27
ENTER_KEY = 10
RAPID_KEYPRESS_THRESHOLD = 30  # Minimum milliseconds between two getch() calls for input to be considered user-based.
SEARCH_PROMPT = "Find: "

# Before initializing curses, remove the Esc key delay from the OS environment.
os.environ.setdefault('ESCDELAY', '0')

# Check for root.
if not admin():
    print "Only user ID #0 (root) can run this program"
    exit(1)


# DEBUG: a junk function for playing with color rendering.
def main2(stdscr):
    # curses.start_color()
    curses.use_default_colors()
    for i in range(0, curses.COLORS):
        curses.init_pair(i + 1, i, -1)
    stdscr.addstr(0, 0, '{0} colors available'.format(curses.COLORS))
    maxy, maxx = stdscr.getmaxyx()
    maxx = maxx - maxx % 5
    x = 0
    y = 1
    stdscr.addstr(12, 0, str(curses.COLORS))
    try:
        for i in range(0, curses.COLORS):
            stdscr.addstr(y, x, '{0:5}'.format(i), curses.color_pair(i))
            x = (x + 5) % maxx
            if x == 0:
                y += 1
    except curses.ERR:
        pass
    stdscr.getch()


# DEBUG: This should be moved below main().
# Initialize Curses (set various parameters, etc).
def initCurses(screen):
    screen.nodelay(True)  # Make getch() non-blocking.
    curses.start_color()  # DEBUG: I'm not sure this does anything...
    curses.use_default_colors()
    # curses.init_pair(1, curses.COLOR_RED, -1)


def main(screen):
    initCurses(screen)  # Set parameters of curses environment.
    devices = list()
    selector = SELECTOR_ABSENT  # Hide the drive selector until drives are found.
    searchString = ""
    searchModeFlag = False  # Toggle search mode (as versus command mode).
    displayTestFlag = False  # Toggle a display properties test.
    redrawScreen = True  # Signal a screen redraw/refresh.
    refreshDevices = True  # Signal a rescan of all the drives.
    messageBarContents = ""  #

    exitFlag = False
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

            # Print the program title.
            screen.addstr(1, 1, "Drive Scanner", curses.A_REVERSE)

            # Print the search bar or help bar.
            if searchModeFlag:
                screen.addstr(POS_BY, POS_BX, SEARCH_PROMPT + searchString)
            else:
                screen.addstr(POS_BY, POS_BX, "(f)ind (d)isplay test (r)efresh (s)hort test (q)uit")

            # Print the message bar.
            screen.addstr(POS_MY, POS_MX, messageBarContents)

            # Print the drive list.
            screen.addstr(POS_DLY - 1, POS_DLX, summaryHeader())
            for y in range(len(devices)):
                screen.addstr(POS_DLY + y, POS_DLX, devices[y].oneLineSummary())

            # Print detailed info for the currently selected device.
            if selector is not SELECTOR_ABSENT:
                screen.addstr(POS_DLY + selector, POS_DLX - 4, "-->")
                device = devices[selector]
                deviceName = device.devicePath  # Refer to the device by its path.
                posX, posY = 1, POS_DLY + len(devices) + 1  # Text position of imaginary cursor.

                # Print the list of failed attributes.
                if device.hasFailedAttributes():
                    screen.addstr(posY, posX, attributeHeader())
                    posY += 1
                    for failedAttribute in device.failedAttributes:
                        screen.addstr(posY, posX, failedAttribute)
                        posY += 1  # Increment vertical cursor
                else:
                    screen.addstr(posY, posX, "No WHEN_FAIL attributes found for " + deviceName)
                    posY += 1  # Increment vertical cursor
                posY += 1  # Add a blank line before next section of info.

                # Print the test history for the device.
                # NOTE: The SMART firmware standard stores up to 21 tests and thereafter starts recording over top
                #       of older tests.
                if len(device.testHistory) > 0:
                    screen.addstr(posY, posX, "History of SMART tests for " + deviceName)
                    posY += 1  # Increment vertical cursor
                    for testResult in device.testHistory:
                        screen.addstr(posY + 1, posX, testResult)
                        posY += 1  # Increment vertical cursorc
                else:
                    screen.addstr(posY, posX, "No history of SMART tests found for " + deviceName)
                    posY += 1  # Increment vertical cursor
                posY += 1  # Add a blank line before next section of info.

            # Draw displaying testing stuff if that mode is active.
            if displayTestFlag:
                screen.addstr(10, 10, " NORMAL ")
                screen.addstr(11, 10, " REVERSE ", curses.A_REVERSE)
                screen.addstr(12, 10, " BLINK ", curses.A_BLINK)
                screen.addstr(13, 10, " BOLD ", curses.A_BOLD)
                screen.addstr(14, 10, " DIM ", curses.A_DIM)
                screen.addstr(15, 10, " STANDOUT ", curses.A_STANDOUT)
                screen.addstr(16, 10, " UNDERLINE ", curses.A_UNDERLINE)
                screen.addstr(17, 10, " COLOR! ", curses.color_pair(1))

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
                elif keypress == ENTER_KEY:
                    selector, messageBarContents = searchDevices(searchString, devices)
                    searchModeFlag = False
                    searchString = ""  # Clear the search string after each search.
                elif keypress == curses.KEY_BACKSPACE:
                    searchString = searchString[:-1]
                elif keypress < 256:  # ASCII keys get added to search.
                    searchString += curses.keyname(keypress)
                else:
                    pass  # All other keys are ignored in search mode.

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

                if keypress == ord('d'):
                    displayTestFlag = not displayTestFlag

                if keypress == ord('s'):
                    if selector is not SELECTOR_ABSENT:
                        devices[selector].runShortTest()
                    refreshDevices = redrawScreen = True

                if keypress == ord('r'):
                    refreshDevices = redrawScreen = True


                if keypress == ord('q'):
                    exitFlag = True

        time.sleep(0.01)  # Sleep for this many seconds to reduce CPU load.


def searchDevices(searchString, devices):
    message = ""  # Default to no message.
    selector = SELECTOR_ABSENT  # Default to hiding the selector.
    # Build a list of search-matching devices and highlight them as selected.
    matchingDevices = list()
    for i in range(len(devices)):
        if devices[i].matchSearchString(searchString):
            matchingDevices.append(devices[i])
            selector = i  # Set selector to matching drive.
    if len(matchingDevices) == 0:
        message = "No drives matched search string."
    if len(matchingDevices) >= 2:
        message = "Search matched multiple drives:"
        for device in matchingDevices:
            message += " " + device.devicePath
            selector = SELECTOR_ABSENT  # Hide the selector if >1 device matched search.
    return selector, message


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
