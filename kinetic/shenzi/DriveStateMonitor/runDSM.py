#!/usr/bin/python
"""
Run DSM
Usage: ./runDSM
Purpose: Makes sure no other DSMs are currently running and then starts
         a new DSM, redirecting output to file
         DriveStateMonitor/Logs/timestamp_DSMLog.txt
"""
import os
import sys
import time
from argparse import ArgumentParser
from subprocess import Popen, STDOUT, PIPE

def get_dsm_pid():
    """
    Will return a list of the process ids for and DSMs running
    """
    pids = []
    proc1 = Popen('ps aux', shell=True, stdout=PIPE)
    proc2 = Popen('grep \'[D]riveStateMonitor.py\'', shell=True,stdin=proc1.stdout,stdout=PIPE)

    proc1.stdout.close()
    out, err = proc2.communicate()
    out = filter(None, out.split("\n"))

    for x in out:
        pids.append(int(x.split()[1]))
    return pids

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.parse_args()

    # Check if DSM is already running
    pids = get_dsm_pid()
    if len(pids) != 0:
        print "[DriveStateMonitor.py is already running]"
        sys.exit(0)

    # Create the Logs directory if it doesn't exist
    dsm_dir_path = os.path.dirname(os.path.realpath(__file__)).split('/')
    command_path = '/'.join(dsm_dir_path+['DriveStateMonitor.py'])
    log_path = '/'.join(dsm_dir_path+['Logs'])
    if log_path:
        if not os.path.exists(log_path):
            os.makedirs(log_path)

    # Create the process and direct output to log file
    log_path = log_path+'/'+time.strftime('%Y-%m-%d_%H-%M-%S')+"_DSMlog.txt"
    with open(log_path, 'w') as file_handle:
        command = ['python','-u', command_path]
        sp = Popen(command, stdout=file_handle, stderr=STDOUT)
    print "[Drive State Monitor has been kicked off. For more information check the log file ("+log_path+")]"