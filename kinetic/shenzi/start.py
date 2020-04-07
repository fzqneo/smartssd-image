#!/usr/bin/python
"""
Start
Usage: drives.csv | ./start.py script.py [args...]
Purpose: Issues the command to start all drives with the given script
         and redirect the output to a file with format
         timestamp_drive_script.csv. Expects all scripts to be python
         and take a command line argument '-s serial_number'
"""
import os
import sys
import time
from subprocess import Popen, STDOUT
from Support.General import get_drive_list_input

SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
RESULTS_PATH = os.path.join(SHENZI_PATH,"Mine","Results")
COMMAND_PREFIX = ['python','-u']

# -------------------------------------------------------------------------------------------------
# Helper Function
# -------------------------------------------------------------------------------------------------
def start_drive(command, script_name):
    """
    Create output file and start drive
    """
    file_name = time.strftime('%Y-%m-%d_%H-%M-%S')+"_"+drive+"_"+script_name+".csv"
    file_name = os.path.join(RESULTS_PATH,file_name.translate(None, "!@#$%^&*()[]{};:,/<>?\|`~=+"))
    with open(file_name, 'w') as file_handle:
        sp = Popen(command, stdout=file_handle, stderr=STDOUT)
        return True
    return False

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # If the help flag is given or the needed data isn't there print help and exit
    if '-h' in sys.argv or len(sys.argv) < 2 or sys.stdin.isatty():
        print  'usage : drives.csv | ./start.py script.py [args...]'+\
                '\n\noptional arguments:\n  -h, --help'+\
                '            show this help message and exit'
        sys.exit(1)

    # Check that the command script exists
    if not os.path.isfile(sys.argv[1]):
        print "[Error on Start: Unable to locate script "+str(sys.argv[1])+"]"
        sys.exit(1)

    # Make sure they didn't try to pass in a serial_number in the args
    for arg in sys.argv:
        if arg in ['--serial_number', '-s']:
            print "[Error, cannot pass the argument "+arg+" to start script]"
            sys.exit(1)

    # Form command and grab script name for output file
    command = COMMAND_PREFIX+sys.argv[1:]
    script_name =  sys.argv[1].replace(".py","")
    success_count = 0
    failed_drives = []

    # Create the results directory if it doesn't exist
    if RESULTS_PATH:
        if not os.path.exists(RESULTS_PATH):
            os.makedirs(RESULTS_PATH)

    # Get and start drives
    drives_to_work, invalid_count = get_drive_list_input()
    for drive in drives_to_work:
        temp_command = command+['-s',drive]
        if start_drive(temp_command, script_name):
            success_count += 1
        else:
            failed_drives.append(drive)
    print "[Start Complete; Invalid serial numbers:"+str(invalid_count)+\
            "Failed:"+str(len(failed_drives))+" Started:"+str(success_count)+"]"
    if failed_drives:
        print "[Failed to Start: "+",".join(failed_drives)+"]"
        sys.exit(1)
