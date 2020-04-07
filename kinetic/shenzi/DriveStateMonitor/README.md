# Drive State Monitor (DSM)

The Drive State Monitor is responsible for monitoring, maintaining, and reporting information about local drive activity.
* Each DSM is only responsible for the system it is being run on
* Each DSM will only operate on system interfaces up upon start up (if you bring up an interface after starting the DSM, but want the DSM to use it, you must restart the DSM)
* You can only run one DSM at a time on any one system (so if another user has one running you share that one instead of running multiples)
* If you want to view drive information from a different system you must run a DSM on that system, and communicate with that DSM's address

## User Interaction

### Starting and Stopping a DSM
You need to run a DSM on any system you want to see drive information for

```
./Shenzi/DriveStateMonitor/runDSM
./Shenzi/DriveStateMonitor/stopDSM
``` 

### Interacting with a DSM 
* __Available Queries:__
    * m : Returns all current multicast data
    * s : Returns complete status history
    * w : Signal to the DSM to wipe all currently stored information
* __Message Protocol:__ [Data | End Byte]
    * Data: The query response, always in JSON format
    * End Byte: '\x04', used to mark the end of a message. If a query has no data, the DSM will still send the end byte to acknowledge the received query
* __Query Address:__
    * Port 2203
    * Can be contacted via any of the system addresses, including local
* __Status Address:__ Where scripts should send status updates
    * Port 3110
    * Can be contacted via any of the system addresses, including local
    * Will store up to 20 statuses for any given device
    * Expected Format for Data: {'serial_number':x, 'time_stamp':y, 'status':z}

### Using MulticastListener.py Independently
Listens for and stores multicast data coming in on any of the system addresses 

Can be run independent from, and concurrent to, the DSM (all data will print to the terminal in JSON format)

```
Usage: python MulticastListener.py [-t time]
       -t : How long the MulticastListener should listen for data before printing it out, default is 5 seconds
``` 

## Development

### Requirments / Standards
* No scripts added to the DriveStateMonitor directory should depend on scripts in any other directory in Shenzi 
* Adhere to the Exit Codes listed below

### Exit Codes
These are the exit code meanings for all scripts in the DriveStateMonitor directory

```
0 : Success
1 : Keyboard Interrupt
2 : Failed to Create Socket
3 : Socket Error on Listen
4 : Internal Kill Switch
```