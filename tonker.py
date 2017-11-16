#!/usr/bin/env python

# Tinker - A temporary program for experimenting with misc features.

import curses
import os
import time

# Drawing positions for view layout.
POS_BX = 4  # Left side of search/help bar.
POS_BY = 4  # Top side of search/help bar.
POS_DLX = 6  # Left side of drive list.
POS_DLY = 8  # Top side of drive list.

SELECTOR_ABSENT = -1
NO_KEYS_PRESSED = -1
ESCAPE_KEY = 27
RAPID_KEYPRESS_THRESHOLD = 30  # Minimum milliseconds between two getch() calls for input to be considered user-based.

# Before initializing curses, remove the Esc key delay from the OS environment.
os.environ.setdefault('ESCDELAY', '0')


def main(screen):
    curses.curs_set(0)  # Make the terminal cursor invisible.
    screen.nodelay(True)  # Make getch() non-blocking.
    drives = ['drive 1', 'drive 2', 'drive 3']
    selector = 0 if len(drives) > 0 else SELECTOR_ABSENT  # Position the selector on the first listed drive.
    searchString = ""
    searchModeFlag = False

    exitFlag = False
    while not exitFlag:
        ######################################
        # Draw the view.                     #
        ######################################
        # Clear the screen
        screen.clear()
        screen.border(0)

        # Draw the program title.
        screen.addstr(2, 2, "Drive Scanner")

        # Draw the search bar or help bar.
        if searchModeFlag:
            screen.addstr(POS_BY, POS_BX, "Find: " + searchString)
        else:
            screen.addstr(POS_BY, POS_BX, "(f)ind (q)uit")

        # Draw the drive list.
        for y in range(len(drives)):
            screen.addstr(POS_DLY + y, POS_DLX + 4, drives[y])

        # Draw the selector.
        if selector is not SELECTOR_ABSENT:
            screen.addstr(POS_DLY + selector, POS_DLX, "-->")

        # Update the view.
        screen.refresh()

        # Check for and handle keypresses.
        keypress = screen.getch()
        if keypress is not NO_KEYS_PRESSED:
            # In search mode keys should be added to the search string until Esc or Enter.
            if searchModeFlag:
                if keypress == ESCAPE_KEY:
                    searchString = ""
                    searchModeFlag = False
                else:
                    searchString += curses.keyname(keypress)

            # When not in search mode, keys are interpreted as commands.
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
                if len(drives) > 0:
                    if keypress == curses.KEY_DOWN:
                        selector = (selector + 1) % len(drives)
                    if keypress == curses.KEY_UP:
                        selector = (selector - 1) % len(drives)
                else:
                    selector = SELECTOR_ABSENT

                if keypress == ord('f'):
                    searchModeFlag = True

                if keypress == ord('q'):
                    exitFlag = True


curses.wrapper(main)

