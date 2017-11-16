#!/usr/bin/env python

# Junk Timer - A throwaway program for experimenting with high precision (<1ms) timers.

import curses
import time


def main(screen):
    searchString = ""
    stopFlag = False
    y = 2
    while not stopFlag:
        start = time.time()
        keypress = screen.getch()
        end = time.time()
        if keypress == ord('q'):
            stopFlag = True
        searchString += curses.keyname(keypress)
        screen.addstr(1, 4, searchString)
        screen.addstr(y, 10, str(int((end - start) * 1000.0)) + "  " + curses.keyname(keypress))
        y += 1


curses.wrapper(main)
