#!/usr/bin/python
"""
Stop DSM
Usage: ./stopDSM
Purpose: Finds and sends a kill signal to the DSM process
"""
import os
import signal
from argparse import ArgumentParser
from runDSM import get_dsm_pid

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.parse_args()

    # Get process ids
    pids = get_dsm_pid()
    count = 0

    # Try to kill each one, handle any OS errors
    for pid in pids:
        try:
            os.kill(pid, signal.SIGINT)
            count += 1
        except OSError as e:
            print "[OSError issuing kill signal to pid "+str(pid)+": "+str(e)+"]"

    # Report kill count
    print "[Killed "+str(count)+" processes]"

