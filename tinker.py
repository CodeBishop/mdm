#!/usr/bin/env python
import curses

SELECTOR_ABSENT = -1


def main(stdscr):
    curses.curs_set(0)  # Make the terminal cursor invisible.
    selector = SELECTOR_ABSENT
    drives = ['drive 1', 'drive 2', 'drive 3']

    exitFlag = False
    while not exitFlag:
        # Draw the view.
        stdscr.clear()
        stdscr.border(0)
        for y in range(len(drives)):
            stdscr.addstr(4 + y, 8, drives[y])
        if selector is not SELECTOR_ABSENT:
            stdscr.addstr(4 + selector, 4, "-->")
        stdscr.refresh()

        # Get user input.
        userKey = stdscr.getch()
        if len(drives) == 0:
            selector = SELECTOR_ABSENT
        else:
            if userKey == curses.KEY_DOWN:
                selector = (selector + 1) % len(drives)
            if userKey == curses.KEY_UP:
                selector = (selector - 1) % len(drives)

        if userKey == ord('q'):
            exitFlag = True

curses.wrapper(main)

