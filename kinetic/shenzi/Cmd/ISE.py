"""
ISE
Usage: python ISE.py -s serial_number [-i interface]
Purpose: Will issue an ISE command and report status.
         In addition to being accessed through command line, it's easy to import and create an
         object and use the start, stop, wait API.
"""
import os
import sys
from argparse import ArgumentParser
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
from Support.ScriptBases import StartWaitStopClientAPI

# Globals -----------------------------------------------------------------------------------------
DEFAULT_INTERFACE = None
DEFAULT_PIN = ""

# -------------------------------------------------------------------------------------------------
# ISE
# -------------------------------------------------------------------------------------------------
class ISE(StartWaitStopClientAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, pin=DEFAULT_PIN):
        super(ISE, self).__init__(serial_number, interface, 'ISE')
        self._client.use_ssl = True
        self.pin = pin

    # Activity thread -----------------------------------------------------------------------------
    def _activity(self):
        # Connect
        print cfg.StrFmt.Notice("connecting client")
        self._client.status_dsm("connecting client")
        result = self._client.connect()
        if result != 0:
            self.status = result
            print cfg.StrFmt.Notice("[Errno "+str(result)+"] failed to connect")
            self._client.status_dsm("[Errno "+str(result)+"] failed to connect")
            self.stop(activity_call=True)
            return

        # Break if kill switch is set
        if self._kill_switch.isSet():
            self.stop(activity_call=True)
            return

        # Issue command
        print cfg.StrFmt.Notice('issuing ISE command')
        self._client.status_dsm("issuing ISE command")
        result = self._client.blocking_cmd('instant_secure_erase', pin=self.pin)

        # Report status
        if result['success']:
            print cfg.StrFmt.Notice('successful ISE')
            self._client.status_dsm("successful ISE")
        else:
            self.status = 320
            print cfg.StrFmt.Notice('[Errno 320] failed ISE command. '+ cfg.StrFmt.ProtoStatus(result['status']))
            self._client.status_dsm('[Errno 320] failed ISE command. '+ cfg.StrFmt.ProtoStatus(result['status']))
        self.stop(activity_call=True)

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Parse Input
    parser = ArgumentParser()
    parser.add_argument("-s", "--serial_number", required=True,
                        help="The serial number of the drive to test on")
    parser.add_argument("-i", "--interface", default=DEFAULT_INTERFACE,
                        help="The interface on the drive to test on")
    parser.add_argument("-p", "--pin", default=DEFAULT_PIN,
                        help="The pin for the ISE")
    args = parser.parse_args()

    ise = ISE(serial_number=args.serial_number, interface=args.interface, pin=args.pin)
    if ise.status < 100:
        try:
            ise.start()
            ise.wait()
        except (KeyboardInterrupt, SystemExit):
            ise.stop()

    if ise.status >= 100:
        sys.exit(1)

