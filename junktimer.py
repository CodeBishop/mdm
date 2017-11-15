#!/usr/bin/env python

# Junk Timer - A throwaway program for experimenting with high precision (<1ms) timers.

import curses
import time

# START DEBUG
stopFlag = False
y = 2
while not stopFlag:
    start = time.time()
    if screen.getch() == ord('q'):
        stopFlag = True
    end = time.time()
    screen.addstr(y, 10, str(int((end - start) * 1000.0)))
    y += 1
# print(end-start)
exit(0)
# END DEBUG
