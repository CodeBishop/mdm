#!/usr/bin/env python2

import curses
from mdmSMART.utils import *


def main(stdscr):
    setupCursesUtils(stdscr)
    printAt(20, 20, "nothing%%%1Red%%%2Green")
    # curses.start_color()
    # curses.use_default_colors()
    for i in range(1, 8):
        curses.init_pair(i, i, 0)
    # stdscr.addstr(0, 0, '{0} colors available'.format(curses.COLORS))
    for i in range(0, 8):
        stdscr.addstr(1, i*2, str(i), curses.color_pair(i))
    for i in range(0, 8):
        stdscr.addstr(2, i*2, str(i), curses.color_pair(i) | curses.A_REVERSE | curses.A_BOLD)

    stdscr.refresh()
    stdscr.getch()

    curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    stdscr.addstr(5, 4, '{0:5}'.format(i), curses.color_pair(1))
    stdscr.refresh()
    stdscr.getch()

curses.wrapper(main)





