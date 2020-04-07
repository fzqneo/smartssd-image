"""
Status Listener
Usage: N/A
Purpose: DSM owns a status listener and uses it to hear script status updates. A script will send
         in data (json format) and the status listener sends back "\x04" to signal success.
"""
import time
import json
import socket
from threading import Thread, Lock

# Globals -----------------------------------------------------------------------------------------
# Global Variables for Socket Configuration
MAX_LISTENER_CONNECTIONS = 128
SOCKET_BUFFER = 64*2**10
SOCKET_TIMEOUT = 30
STATUS_SOCK_ADDR = ('0.0.0.0',3110)

# -------------------------------------------------------------------------------------------------
# Status Listener
# -------------------------------------------------------------------------------------------------
class StatusListener(object):
    def __init__(self, status_entry_limit=""):
        # Empty string so there is no limit by default
        # This is to limit entries for each serial number
        self.status_entry_limit = status_entry_limit
        
        self._data_lock = Lock()
        self._data = {}
        self._socket = None

    def listen(self, timeout=""):
        """
        Listen for status data for configurable time and spawn thread to store it
        Default is empty string so that the while statement becomes a while True
        because strings will always evaluate to being greater than numbers
        """

        # Initialize the socket
        self._socket = self._initialize_socket()
        if self._socket == None:
            return 2
        self._socket.settimeout(min(SOCKET_TIMEOUT,timeout))
        start_t = time.time()

        # While you haven't timed out listen for statuses
        while time.time()-start_t < timeout:
            try:
                client_sock, addr = self._socket.accept()
                try:
                    msg = json.loads(client_sock.recv(SOCKET_BUFFER))

                # Handle incorrect data formatting
                except ValueError as e:
                    print self._notice("ValueError on Status From "+str(addr[0])+": "+str(e))
                    continue
                t = Thread(target=self._store_data, args=(msg,))
                t.daemon = True
                t.start()
                client_sock.sendall("\x04")
                client_sock.close()

        # Handle socket exceptions
            except socket.timeout:
                pass
            except socket.error as e:
                print self._notice("Socket Error on Listen.\n "+str(e))
                return 3
        try:
            self._socket.close()
        except socket.error:
            pass
        return 0

    def get_data(self):
        """
        Return current dictionary of status data
        """
        with self._data_lock:
            return self._data

    def wipe_data(self):
        """
        Remove all currently stored status data
        """
        with self._data_lock:
            self._data = {}

    def _initialize_socket(self):
        # Creates the status socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_IP, socket.IP_TOS, 8)
            sock.bind((STATUS_SOCK_ADDR))
            sock.listen(MAX_LISTENER_CONNECTIONS)
            return sock
        except socket.error as e:
            print self._notice("Socket Error on Creation."+str(e))
            return None

    def _notice(self, msg):
        # notice statement generator
        return "["+time.strftime('%Y/%m/%d_%H:%M:%S')+" Status Listener: "+\
                str(msg).translate(None, "[]\n")+"]"

    def _store_data(self, status_message):
        # Structure the status update and store it
        with self._data_lock:
            if status_message['serial_number'] not in self._data:
                self._data[status_message['serial_number']] = []
            else:
                while len(self._data[status_message['serial_number']]) >= self.status_entry_limit:
                    del self._data[status_message['serial_number']][0]
            self._data[status_message['serial_number']].append({'time_stamp':status_message['time_stamp'],
                                                               'status':status_message['status']})