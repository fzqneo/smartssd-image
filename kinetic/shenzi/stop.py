#!/usr/bin/python
"""
Stop
Usage: drives.csv | ./stop.py [-d descriptor] [--force]
        d : Adds an additonal descriptor to grep for, when finding processes to stop
        force : send a SIGKILL signal to all processes instead of SIGINT
Purpose: Issues the SIGINT signal to all processes running on any of the given drives
"""
import os
import sys
import signal
from subprocess import Popen, PIPE
from argparse import ArgumentParser
from Support.General import get_drive_list_input

# -------------------------------------------------------------------------------------------------
# Helper Function
# -------------------------------------------------------------------------------------------------
def stop_drive(drive, descriptor='\"\"', force=False):
    """
    Grabs all processes running on that drive that can be greped with the script variable
    and issues a kill command. Returns a count of kill signals issued
    """

    # Get process ids
    search = '\"['+drive[0]+']'+drive[1:]+'\"'

    proc1 = Popen('ps aux', shell=True, stdout=PIPE)
    proc2 = Popen('grep '+search, shell=True,stdin=proc1.stdout,stdout=PIPE)
    proc3 = Popen('grep '+descriptor, shell=True,stdin=proc2.stdout,stdout=PIPE)

    proc1.stdout.close()
    proc2.stdout.close()
    out, err = proc3.communicate()
    out = filter(None, out.split("\n"))
    count = 0

    # Issue kill signal to all processes
    for x in out:
        try:
            if force:
                os.kill(int(x.split()[1]), signal.SIGKILL)
            else:
                os.kill(int(x.split()[1]), signal.SIGINT)
            count += 1
        except OSError as e:
            print "[OSError issuing kill signal to drive "+str(drive)+", pid "+str(x.split()[1])+": "+str(e)+"]"
    return count

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Input Arguments
    parser = ArgumentParser(usage='drives.csv | ./stop.py [-d descriptor]')
    parser.add_argument("-d", "--descriptor", help="Adds an additonal descriptor to grep for,"+\
                                                " when finding processes to stop", default='\"\"')
    parser.add_argument("--force", help="Send a SIGKILL signal to proccesses (instead of SIGINT)", action="store_true")
    args = parser.parse_args()

    # Check that there is data being piped in
    if sys.stdin.isatty():
        print parser.print_help()
        sys.exit(1)

    # Get and stop drives
    success_count = 0
    drives_to_work, invalid_count = get_drive_list_input()
    for drive in drives_to_work:
        success_count += stop_drive(drive, args.descriptor, args.force)
    print "[Stop Complete; Invalid serial numbers:"+str(invalid_count)+\
            " Stopped:"+str(success_count)+"]"