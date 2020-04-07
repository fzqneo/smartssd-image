"""
Drive State Monitor
Usage: python DriveStateMonitor.py
Purpose: Intended to run as a background process, continuously listening for
         multicast messages from kinetic drives, status updates from scripts
         and storing the information while listening for queries for that info.
"""
import sys
import time
import json
import socket
import datetime
from threading import Thread, Event
from StatusListener import StatusListener
from MulticastListener import MulticastListener

# Globals -----------------------------------------------------------------------------------------
# A worker won't be recovered more than (WORKER_RECOVERY_COUNT) times within (WORKER_RECOVERY_TIMOUT)
# seconds and if that threshold is passed then the DSM will die
WORKER_RECOVERY_TIMOUT = 86400 # 86400 seconds = 24 hours
WORKER_RECOVERY_COUNT = 5

# Max number of statuses to hold for any given drive
STATUS_ENTRY_LIMIT = 20 

# Global Variables for Socket Configuration
MAX_LISTENER_CONNECTIONS = 128
SOCKET_BUFFER = 64*2**10
SOCKET_TIMEOUT = 10
QUERY_SOCK_ADDR = ('0.0.0.0',2203)

# -------------------------------------------------------------------------------------------------
# Drive State Monitor
# -------------------------------------------------------------------------------------------------
class DriveStateMonitor(object):
    def __init__(self):
        self._kill_switch = Event()
        self._socket = self._initialize_socket()
        self._workers = {'Multicast':{'object':MulticastListener(),
                                  'time_card':[],
                                  'task':Thread(),
                                  'manager':Thread()},
                         'ScriptStatus':{'object':StatusListener(STATUS_ENTRY_LIMIT),
                                  'time_card':[],
                                  'task':Thread(),
                                  'manager':Thread()}}

    def start(self):
        """
        Check if query socket was initialized and start listening
        """
        if not self._socket:
            return 2
        self._hire_managers()
        return self._listen()

    def _listen(self):
        # Listen for queries and respond accordingly
        while not self._kill_switch.is_set():
            try:

                # Wait for connection
                client_sock, addr = self._socket.accept()
                addr = addr[0]
                query = (client_sock.recv(SOCKET_BUFFER))
                if self._kill_switch.is_set():
                    break

                # Spawn a thread to respond to query
                t = Thread(target=self._process_query,args=(client_sock, addr, query),
                           name="DSM  query response to "+str(addr))
                t.daemon = True
                t.start()

            # Handle socket errors
            except socket.timeout:
                pass
            except socket.error as e:
                print self._notice("Socket Error on Listen."+str(e))
                return 3
        return 4

    def _process_query(self, client_sock, addr, query):
        # Respond to each query appropriately
        data_package = "DSM Query Error: Invalid Query. Please Try:"+\
                        " m (multicast data), s (status history), or w (wipe data)\x04"

        # Wipe DSM
        if query == 'w':
            print self._notice("Received wipe command from "+str(addr))
            for worker in self._workers:
                self._workers[worker]['object'].wipe_data()
            data_package = "Wipe DSM Success\x04"

        # Multicast
        elif query == 'm':
            data_package = json.dumps(self._workers['Multicast']['object'].get_data())+"\x04"
            
        # Status
        elif query == 's':
            data_package = json.dumps(self._workers['ScriptStatus']['object'].get_data())+"\x04"

        # Send requested data
        try:
            client_sock.sendall(data_package)
            client_sock.close()
        except socket.error as e:
            print self._notice("Socket Error on Sending Data to "+str(addr)+"."+str(e))

    def _hire_managers(self):
        # Initialize and start all managers
        for worker in self._workers:
            self._workers[worker]['manager'] = Thread(target=self._manage,args=(worker,),
                                                      name="DSM "+worker+" Manager")
            self._workers[worker]['manager'].daemon = True
            self._workers[worker]['manager'].start()

    def _manage(self, worker):
        # Start and maintain the task threads, give up if they died too many times too quickly
        give_up = False
        while not give_up:

            # Initialize worker with a task and time stamp and wait for it to finish
            try:
                if not self._workers[worker]['task'].is_alive():
                    self._workers[worker]['task'] = Thread(target=self._workers[worker]['object'].listen,
                                                            name="DSM "+worker+" task thread")
                    self._workers[worker]['task'].daemon = True
                    self._workers[worker]['task'].start()
                    t = time.time()
                    self._workers[worker]['time_card'].append(t)
                    print worker+" Startup: "+\
                          datetime.datetime.fromtimestamp(t).strftime('%Y/%m/%d %H:%M:%S')
                self._workers[worker]['task'].join()
            except:
                pass

            # If you've exceeded the limit of allowable failures give up
            try:
                if self._workers[worker]['time_card'][-1]-self._workers[worker]['time_card'][-(WORKER_RECOVERY_COUNT)] <= WORKER_RECOVERY_TIMOUT:
                    print self._notice(worker+" Exceeded WORKER_RECOVERY_COUNT & WORKER_RECOVERY_TIMOUT")
                    give_up = True
            except IndexError:
                pass

        # If the worker could not be managed, signal the DSM to die
        self._kill_switch.set()

    def _notice(self, msg):
        # notice statement generator
        return "["+time.strftime('%Y/%m/%d_%H:%M:%S')+" DSM: "+\
                str(msg).translate(None, "[]\n")+"]"

    def _initialize_socket(self):
        # Creates the query socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_IP, socket.IP_TOS, 8)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.bind((QUERY_SOCK_ADDR))
            sock.listen(MAX_LISTENER_CONNECTIONS)
            return sock
        except socket.error as e:
            print self._notice("Socket Error on Creation."+str(e))
            return None
# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        dsm = DriveStateMonitor()
        x = dsm.start()
        sys.exit(x)
    except KeyboardInterrupt:
        sys.exit(1)