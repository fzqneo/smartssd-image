"""
Firmware Update
Usage: python FirmwareUpdate.py -s serial_number -f firmware_file.slod [-i interface]
Purpose: Will issue a firmware update command and monitor the drive as it restarts.
         In addition to being accessed through command line, it's easy to import and create an
         object and use the start, stop, wait API.
"""
import os
import sys
import time
import subprocess
from argparse import ArgumentParser
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
from Support.ScriptBases import StartWaitStopClientAPI

# Globals -----------------------------------------------------------------------------------------
PING_TIMEOUT = 300 # How long a drive can take to go down / come back
NOOP_TIMEOUT = 60 # How long, after a drive is pingable, to wait for kinetic to respond

DEFAULT_INTERFACE = None

# -------------------------------------------------------------------------------------------------
# Firmware Update
# -------------------------------------------------------------------------------------------------
class FirmwareUpdate(StartWaitStopClientAPI):
    def __init__(self, serial_number, firmware_file, interface=DEFAULT_INTERFACE):
        super(FirmwareUpdate, self).__init__(serial_number, interface, 'FirmwareUpdate')
        self._firmware_file = firmware_file

        if self.status < 100:
            print cfg.StrFmt.Notice("Configuration", "interface: "+str(interface)+\
                                                     ", firmware_file: "+str(self._firmware_file))

    def stop(self, activity_call=False):
        print cfg.StrFmt.Notice('stopping '+self.script_name)
        self._stop_called.set()
        self._kill_switch.set()
        if self._activity_thread.isAlive() and not activity_call:
            self._activity_thread.join(30)
        if self._client.is_connected:
            print cfg.StrFmt.Notice('closing client')
            self._client.close()
        if self.status < 100:
            self.status = 0
        print cfg.StrFmt.Notice('stopped '+self.script_name)
        self._client.status_dsm('stopped '+self.script_name)
        self._stop_complete.set()

    # Activity thread -----------------------------------------------------------------------------
    def _activity(self):
        # Open file and issue command
        result = self._issue_command()
        if not result['success']:
            if self.status != 330:
                self.status = 331
            print cfg.StrFmt.Notice("[Errno "+str(self.status)+"] failed firmware update. "+cfg.StrFmt.ProtoStatus(result['status']))
            self._client.status_dsm("[Errno "+str(self.status)+"] failed firmware update. "+cfg.StrFmt.ProtoStatus(result['status']))
            self.stop(activity_call=True)
            return

        # Monitor the drive going down / coming back
        print cfg.StrFmt.Notice("waiting for drive to go down")
        self._client.status_dsm("waiting for drive to go down")
        if not self._ping_state_change(True):
            if not self._kill_switch.isSet():
                self.status = 332
                print cfg.StrFmt.Notice("[Errno 332] failed firmware update")
                self._client.status_dsm("[Errno 332] failed firmware update")
            self.stop(activity_call=True)
            return

        print cfg.StrFmt.Notice("waiting for drive to come back")
        self._client.status_dsm("waiting for drive to come back")
        if not self._ping_state_change(False):
            if not self._kill_switch.isSet():
                self.status = 333
                print cfg.StrFmt.Notice("[Errno 333] failed firmware update")
                self._client.status_dsm("[Errno 333] failed firmware update")
            self.stop(activity_call=True)
            return
        print cfg.StrFmt.Notice("drive responds to ping")
        self._client.status_dsm("drive responds to ping")

        # Try to communicate with kinetic
        if not self._noop_drive():
            if not self._kill_switch.isSet():
                self.status = 334
                print cfg.StrFmt.Notice("[Errno 334] failed firmware update")
                self._client.status_dsm("[Errno 334] failed firmware update")
            self.stop(activity_call=True)
            return

        print cfg.StrFmt.Notice("kinetic is responsive")
        self._client.status_dsm("kinetic is responsive")
        self._client.status_dsm("completed firmware update")

        self.stop(activity_call=True)

    # Helper methods ------------------------------------------------------------------------------
    def _issue_command(self):
        """
        Open file and issue command to drive
        """
        rv = {'success':False, 'status': ""}
        # Read firmware file
        print cfg.StrFmt.Notice("read in firmware file : "+os.path.split(self._firmware_file)[1])
        self._client.status_dsm("read in firmware file : "+os.path.split(self._firmware_file)[1])
        try:
            f = open(self._firmware_file).read()
        except IOError:
            self.status = 330
            rv['status'] = "failed to open/read firmware file"
            return rv
        # Connect
        result = self._client.connect()
        if result != 0:
            self.status = result
            rv['status'] = "failed to connect"
            return rv
        # Issue command
        print cfg.StrFmt.Notice("issuing command")
        self._client.status_dsm("issuing command")
        results = self._client.blocking_cmd('update_firmware', firmware=f)
        self._client.close()
        if not results['success']:
            rv['status'] = str(results['cmd'].status)
        else:
            rv['success'] = True
        return rv

    def _noop_drive(self):
        """
        Try to connect and issue noop to a drive
        Returns True upon success and False on failure
        """
        x = self._client.verbosity
        self._client.verbosity = 0
        t0 = time.time()
        while time.time()-t0 <= NOOP_TIMEOUT and not self._kill_switch.is_set():
            if not self._client.is_connected:
                if self._client.connect(max_attempts=1) !=0:
                    continue
            temp = self._client.blocking_cmd('noop')
            if temp['success']:
                self._client.verbosity = x
                return True
        self._client.verbosity = x
        return False

    def _ping_state_change(self, state):
        """
        Given a state (true = successful ping, false = unsuccessful ping) keeping pinging the
        drive until it changes state or times out
        """
        t0 = time.time()
        while time.time()-t0 <= PING_TIMEOUT and not self._kill_switch.is_set():
            if self._ping_drive() != state:
                return True
        return False

    def _ping_drive(self):
        """
        Issues a ping command to the drive and returns True for success or False for failure
        """
        with open(os.devnull, 'w') as out:
            # Get ip address information for drive
            x = self._client.verbosity
            self._client.verbosity = 0
            mcast_info = self._client.retrieve_mcast_info()['response']['ip_list']
            self._client.verbosity = x

            # Issues 1 ping and waits up to 2 seconds for a response
            for ip in mcast_info:
                results = subprocess.Popen(["ping","-c","1","-W","2", ip], stdout=out, stderr=out).wait()
                if results is 0:
                    return True
                else:
                    return False
            return False

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Parse Input
    parser = ArgumentParser()
    parser.add_argument("-s", "--serial_number", required=True,
                        help="The serial number of the drive to test on")
    parser.add_argument("-f", "--firmware", required=True,
                        help="The path to the slod file to download")
    parser.add_argument("-i", "--interface", default=DEFAULT_INTERFACE,
                        help="The interface on the drive to test on")
    args = parser.parse_args()

    fwu = FirmwareUpdate(args.serial_number, args.firmware, args.interface)

    if fwu.status < 100:
        try:
            fwu.start()
            fwu.wait()
        except (KeyboardInterrupt, SystemExit):
            fwu.stop()

    if fwu.status >= 100:
        sys.exit(1)
