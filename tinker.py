#!/usr/bin/env python
import curses


def main(stdscr):
    exitFlag = False
    while not exitFlag:
        stdscr.clear()
        stdscr.border(0)
        stdscr.addstr(2, 2, "Please enter a number...")
        stdscr.addstr(4, 4, "1 - Add a user")
        stdscr.addstr(4, 4, "2 - Restart Apache")
        stdscr.addstr(6, 4, "3 - Show disk space")
        stdscr.addstr(7, 4, "4 - Exit")
        stdscr.refresh()

        x = stdscr.getch()

        if x != '':
            exitFlag = True

curses.wrapper(main)

