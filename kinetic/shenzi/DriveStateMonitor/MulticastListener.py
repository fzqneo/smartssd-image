"""
Multicast Listener
Usage: python MulticastListener.py [t='time interval']
        t : how long (in seconds) to listen for multicast and then report
Purpose: DSM owns a multicast listener and uses it to hear kinetic multicast
         on all interfaces. Concurrently the Multicast Listener can be used
         as a stand-alone script to spit out all multicast data it hears after
         some amount of time.
"""
import re
import sys
import json
import time
import socket
from threading import Thread, Lock
from subprocess import Popen, PIPE
from argparse import ArgumentParser

# Globals -----------------------------------------------------------------------------------------
DEFAULT_LISTEN_TIME = 5 # Only used as default if name == main

# Global Variables for Socket Configuration
MAX_LISTENER_CONNECTIONS = 128
SOCKET_BUFFER = 64*2**10
SOCKET_TIMEOUT = 2
MCAST_ADDR = '239.1.2.3'
MCAST_PORT = 8123

# -------------------------------------------------------------------------------------------------
# Multicast Listener
# -------------------------------------------------------------------------------------------------
class MulticastListener(object):
    def __init__(self):
        self._data_lock = Lock()
        self._data = {}
        self._socket = None

    def listen(self, timeout=""):
        """
        Grab mcast data for configurable time and spawn thread to store it
        Default is empty string so that the while statement becomes a while True
        because strings will always evaluate to being greater than numbers
        """

        # Initialize socket
        self._socket = self._initialize_socket()
        if self._socket == None:
            return 2
        self._socket.settimeout(min(SOCKET_TIMEOUT,timeout))
        start_t = time.time()

        # While you haven't timed out listen for mcast
        while time.time()-start_t < timeout:
            try:
                msg = json.loads(self._socket.recv(SOCKET_BUFFER))
                t = Thread(target=self._store_data, args=(msg,))
                t.daemon = True
                t.start()

        # Handle socket exceptions
            except socket.timeout:
                pass
            except socket.error as e:
                print self._notice("Socket Error on Listen."+str(e))
                return 3
        try:
            self._socket.close()
        except socket.error:
            pass
        return 0

    def get_data(self):
        """
        Return current dictionary of mcast data
        """
        with self._data_lock:
            return self._data

    def wipe_data(self):
        """
        Remove all currently stored mcast data
        """
        with self._data_lock:
            self._data = {}

    def _notice(self, msg):
        # notice statement generator
        return "["+time.strftime('%Y/%m/%d_%H:%M:%S')+" Multicast Listener: "+\
                str(msg).translate(None, "[]\n")+"]"

    def _store_data(self, mcast_message):
        # Add a time stamp to the data and store it
        time_stamp = time.time()
        mcast_message['last_seen'] = time.strftime("%Y %b %d %H:%M:%S")
        with self._data_lock:
            self._data[mcast_message['serial_number']]= mcast_message

    def _initialize_socket(self):
        # Creates the mcast socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', MCAST_PORT))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            ip_list = self._get_ips()
            for ip in ip_list:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,socket.inet_aton(MCAST_ADDR)+socket.inet_aton(ip))
            return sock
        except socket.error as e:
            print self._notice("Socket Error on Creation."+str(e))
            return None

    def _get_ips(self):
        # Get all IPs of all interfaces on the system
        p = Popen(['ip a'], shell=True, stdout=PIPE)
        ip_list = re.findall(r"inet \b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", p.communicate()[0])
        for index, item in enumerate(ip_list):
            ip_list[index] = item.replace("inet ","")
        return ip_list

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-t", "--time", type=float, default=DEFAULT_LISTEN_TIME,
                         help="How long to gather mcast before printing")
    args = parser.parse_args()
    try:
        ml = MulticastListener()
        x = ml.listen(args.time)
        print json.dumps(ml.get_data(), indent=4, separators=(',', ':'))
        sys.exit(x)
    except KeyboardInterrupt:
        sys.exit(1)
