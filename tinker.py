#!/usr/bin/env python

# Tinker - A temporary program for experimenting with misc features.

import curses

# Drawing positions for view layout.
POS_BX = 4  # Left side of search/help bar.
POS_BY = 4  # Top side of search/help bar.
POS_DLX = 6  # Left side of drive list.
POS_DLY = 8  # Top side of drive list.

SELECTOR_ABSENT = -1

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
            screen.addstr(POS_BY, POS_BX, "Find: ")
            screen.addstr(POS_BY, POS_BX + len("Find: "), searchString)
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

        # Get user input.
        userKey = screen.getch()
        if len(drives) == 0:
            selector = SELECTOR_ABSENT
        else:
            if userKey == curses.KEY_DOWN:
                selector = (selector + 1) % len(drives)
            if userKey == curses.KEY_UP:
                selector = (selector - 1) % len(drives)

        if userKey == ord('f'):
            searchModeFlag = True

        if userKey == ord('q'):
            exitFlag = True

curses.wrapper(main)

