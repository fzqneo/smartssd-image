# Introduction and Overview
Shenzi is a mechanism to discover, run workloads, and status drives

```
Shenzi
│
├─── DriveStateMonitor
│     └-- Responsible for monitoring, maintaining, and
│         reporting information about drives on the system
│         it's being run (multicast, script status, and
│         eventually drive location)
│
├─── Support
│     ├-- Scripts that are owned, not invoked. They offer
│     │   generally useful functionality to be leveraged
│     │   throughout Shenzi and its sub-directories
│     │
│     └─── Keys
│           └-- Various Key Generator config files
│
├─── Cmd
│     └-- Scripts that accomplish a specific task/command
│         and then return
│
├─── KineticQualification
│     └-- All scripts used to create and run qualification
|         testing for Kinetic code
│
├─── Perf
│     └-- Scripts that exercise the drive and report
│         performance data
│
├─── Unit
│     └-- Unit tests developed for targeted testing on
│         kinetic drives
│
└─── Mine
      ├-- This folder is meant for personal user
      │   development. User scripts, Shenzi's config
      │   file, and other user data
      │
      ├-- Config.py : basic configurations to run Shenzi with
      │
      ├─── Results
      │     └-- Any script started with
      │         Shenzi/start.py will output a
      │         results file here
      │
      └─── DriveLists
            └-- A Place to save drive sets for repeated
                reference. mine.csv is a file name with
                special meaning. For more info, please
                read into getDriveList.py
```

---

# Installation
Python 2.7.x (Python 3.x is not supported).

The Latest Kinetic Python Client. If you are on Seagate LCO's LAN, it can be cloned with:

```
git clone ssh://git@http://lco-esd-cm01.colo.seagate.com:7999/kt/python-client.git
```

---

# Getting Started with Shenzi
1. Start a Drive State Monitor on the System you Want to Monitor Drives on:

    ```
    ./Shenzi/DriveStateMonitor/runDSM.py
    ```
2. Start Issuing Commands (look at __Intro Commands__ for a list with examples)

---

# Drive State Monitor (DSM)
The Drive State Monitor is responsible for monitoring, maintaining, and reporting information about local drive activity.

* Each DSM is only responsible for the system it is being run on
* Each DSM will only operate on system interfaces up upon start up (if you bring up an interface after starting the DSM, but want the DSM to use it, you must restart the DSM)
* You can only run one DSM at a time on any one system (so if another user has one running you share that one instead of running multiples)
* If you want to view drive information from a different system you must run a DSM on that system, and communicate with that DSM's address

__See the README.md in the DriveStateMonitor Directory for more Information__

---

# Intro Commands

## Getting Drive Information (getDriveList.py)
This command is the command line interface to the local DSM. It queries the local DSM and gives you the combined drive information in csv format. By default this script will only display information in file Mine/DriveLists/mine.csv. If that file can't be read (doesn't exist, is locked, etc.), this script will display information for all drives the DSM returns. On a clean shenzi install, the file mine.csv does not exist, so it will display all drives the DSM returns. If you have a mine.csv file but wish to see all of the drives, feed in the --all flag (described in the usage statement).

```
Get Drive List
Usage: [drives] | ./get_drive_list.py [-[c ? g ? l ? m ? s] | -S 'x' | -C] --all
        drives : an optional list of drives to show status for
        all : Display information for all drives the DSM has data on.
              If a drive list is pipped in, this flag is ignored.
              If there's a failure to read mine.csv and nothing is pipped in, this flag is automatically set
        -c : Chassis data
        -g : Getlog data, this will output get_log(messages) to a file in the Results directory
        -l : Slot location
        -m : Multicast data
        -s : Most recent script status
        -S : The 'x' most recent status updates, default show all
        -C : Raw bmc data (not mapped to serial_numbers in multicast)
```
### Basic Usage Examples
using a test drive subset (serial numbers A, B, C, and D)

```
# Get general information for drives listed in mine.csv (or all available if no mine.csv exists)
  ./getDriveList.py

# Get general information for my test drives (two ways to do the same thing)
  echo A, B, C, D | ./getDriveList.py
  cat testDrives.csv | ./getDriveList.py

# Get the last 4 available statuses for drives listed in mine.csv (or all available if no mine.csv exists)
  ./getDriveList.py -S 4

# Get all multicast data and the most recent status for drives listed in mine.csv (or all available if no mine.csv exists)
  ./getDriveList.py -sm
```
## Issuing command to Hollywood chassis
Issue commands to the hollywood chassis

```
usage: hollywood.py [-info | -set_fan_speed SET_FAN_SPEED | -power {ON,OFF}] [--location LOCATION]
        -info : get information about the chassis
        -set_fan_speed SET_FAN_SPEED : set the fan speed on the chassis. Must be in this range [20, 100]
        -power {ON,OFF} : issue a power command to a set of drives, a slot, or an entire chassis
        -location LOCATION : an option to issue a power command on a specific slot in a specific bmc. format [ip]:[slot]
```
### Basic Usage Examples
using a test drive subset (serial numbers A, B, C, and D)

```
# Get general information on the chassis
  ./hollywood.py -info

# Issue power off to a set of drives
  echo A, B, C, D | ./hollywood.py -power off

# Issue power on to a bmc at ip 127.0.0.1 and slot 5
  ./hollywood.py -power on 127.0.0.1:5
```
## Starting and Stopping Workloads
### ./start.py
This command is useful for running multiple drives at once and automatically redirecting output to results files located in _Shenzi/Mine/Results_

```
Usage: drives.csv | ./start.py script.py [args...]
```
* __REQUIREMENTS:__ All scripts run using ./start.py must have the following
    * Be a python script
    * Take a command line argument '-s serial_number' or '--serial_number serial_number'

### ./stop.py
Will find all processes with the drive serial name (and optionally a second descriptor -d) in the name and issue kill signals

```
Usage: drives.csv | ./stop.py [-d descriptor] [--force]
       d : Adds an additional descriptor to grep for when finding processes to stop
       force : send a SIGKILL signal to all processes instead of SIGINT
```
## Wiping the DSM of all data
### ./wipeDSM.py
A shortcut script to wipe all multicast data and status histories from the local DSM

```
Usage: ./wipeDSM.py
```
## Creating Drive Sets
All scripts with the __dl__ prefix are intended to help create drive lists through basic set manipulation

### Available manipulations
#### Difference

```
Usage: A.csv | ./dlDiff.py [-f B.csv] [-d descriptor]
       A : A CSV containing set A
       f : A CSV containing set B
       d : What descriptor to use as a primary key
Purpose: Prints out list A-B using A's header. If no set B is fed in then it
         will print A-A (nothing)
```
#### Intersect

```
Usage: A.csv | ./dlIntersect.py [-f B.csv] [-d descriptor]
       A : A CSV containing set A
       f : A CSV containing set B
       d : What descriptor to use as a primary key
Purpose: Show me the drives common between lists A and B. If no set B
         is fed in then it will give A intersect A (which is just A)
```
#### Project

```
Usage: A.csv | ./dlProject.py 'attr_a', 'attr_b',..,'attr_n'
       A : A CSV containing set A
Purpose: Given a combination of attributes it will display those attributes for all
         drives that have them in list A (I only want to see the serial numbers and
         firmware versions of list A). If no attributes are listed it will return A
```
#### Sort

```
Usage: A.csv | ./dlSort.py 'attr_a', 'attr_b',..,'attr_n'
        A : A CSV containing set A
Purpose: It will sort the input in order of the attributes passed in.If no
         attributes are listed it will return A.
```
#### Union

```
Usage: A.csv | ./dlUnion.py [-f B.csv] [-d descriptor]
       A : A CSV containing set A
       f : A CSV containing set B
       d : What descriptor to use as a primary key
Purpose: Combine lists A and B using A's header, eliminate duplicates. If there
         are duplicates, the last item in A will persist. If no set B is fed in,
         it will return A union A (A without duplicates)
```
### Basic Usage Examples

```
# Save off a list of the current drives to use later but only care about serial numbers and ip addresses
  ./getDriveList.py | ./dlProject.py serial_number, *ipv4_addr > Mine/DriveLists/drives.csv

# Get general information for all drives except those in drives.csv
  ./getDriveList.py | ./dlDiff.py -f Mine/DriveLists/drives.csv

# Get both of the drive sets being tested on
  cat testSetA.csv | ./dlUnion.py -f testSetB.csv
```

---

# Available Scripts
There are already a set of scripts written for convenience. In the diagram at the top of this page you can find a description of the various categories of scripts available. As required, these scripts all take a serial number and then get connection information from the local DSM. __These scripts can only reach local drives.__

## Script Status Codes
All given scripts have a public attribute called status that helps give information on it's activity. These are the status code meanings.
* The exit code for the process (if script is called through main) is 0 if the status is 0-99, and 1 if the status is 100 or greater
* Only the most recent status is maintained. For example, if you start a drive (002) and then there is a socket error to the DSM (01X) you would only see the socket error status 01X
* For a more detailed view on script status watch for script output.

```
0XX : Non-Failing Activity
    00x : Script states
        000 : Stopped without errors
        001 : Initialized and not run
        002 : Started
    01X : Communicate with DSM
        010 : Socket failed create/connect
        011 : Socket failed on send
        012 : Socket failed on receive
        013 : Socket failed handshake
        014 : Received Error message in DSM response

2XX : Shenzi Client
    20X : Connect
        200 : Timed out on connection attempts
        201 : Serial number mismatch upon connection
    21X : Retrieve Mcast Info
        210 : Received unexpected data type in DSM multicast query response
        211 : Failed to find connection info in DSM data

3XX : Script
    30X : General Script Errors
        300 : Unknown exception in activity
    31X : Key & Value
        310 : Failed to validate drive limits(key/value size)
        311 : Failed to create key generator
        312 : Key exception during get_next_key()
    32X : ISE script
        320 : Failed ISE command
    33X : Firmware Update Script
        330 : Couldn't open firmware file
        331 : Failed firmware update command
        332 : Timed out / stopped script waiting for drive to go down
        333 : Timed out / stopped script waiting for drive to come back
        334 : Timed out / stopped script trying to connect / noop
    34X : Puts Script
    35X : Gets Script
        350 : Failed to get last key
    36X : Batches Script
    37X : OVS Scripts
        370 : Failed to connect all clients
```
