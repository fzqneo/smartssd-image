"""
Gets
Usage: python Gets.py -s serial_number [-i interface] [-r reporting_interval in seconds]
                                       [-k key_gen config file]
Purpose: Will issue Gets until a key fails for being larger than the last key on the drive.
         In addition to being accessed through command line, it's easy to import a GetScript
         object and use the start, stop, wait API.
"""
import os
import sys
import time
from argparse import ArgumentParser
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
sys.path.insert(0,SHENZI_PATH)
import Mine.Config as cfg
from Support.ShenziClient import kinetic_pb2
from Support.ScriptBases import StartWaitStopPerfAPI
from Support.KeyGenerator import KeyGeneratorException

# Globals -----------------------------------------------------------------------------------------
QUEUE_DEPTH = 32

DEFAULT_INTERFACE = None
DEFAULT_REPORTING_INTERVAL = 60
DEFAULT_KEY_GEN = os.path.join(SHENZI_PATH,"Support","Keys","FixedSequential")
DEFAULT_MAX_NUM_OPS = max

# -------------------------------------------------------------------------------------------------
# Gets
# -------------------------------------------------------------------------------------------------
class Gets(StartWaitStopPerfAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                 keygen_config=DEFAULT_KEY_GEN, max_num_ops=DEFAULT_MAX_NUM_OPS):
        super(Gets, self).__init__(serial_number, interface, reporting_interval, keygen_config, max_num_ops, 'Gets')
        self.end_key = None

        # Print out the configuration details
        configuration = "interface: "+str(interface)
        configuration += ", reporting_interval: "+str(reporting_interval)
        if max_num_ops != DEFAULT_MAX_NUM_OPS:
            configuration += ", max_num_ops: "+str(max_num_ops)
        configuration += ", key.type: "+str(self.key_gen.type)
        for item in self.key_gen.original_specs:
            configuration += ", key."+item+": "+str(self.key_gen.original_specs[item])
        print cfg.StrFmt.Notice("Configuration", configuration)

        # Validate limits (key sizes)
        result = self._validate_limits(maxKeySize=self.key_gen.max_key_size)
        if not result['success']:
            self.status = 310
            print cfg.StrFmt.Notice('[Errno 310] '+str(result['response']))
            self._client.status_dsm('[Errno 310] Failed limit validation')

    # Activity thread -----------------------------------------------------------------------------
    def _activity(self):
        op_count = 0
        try:
            # Keep trying until kill switch is set or a failure in setup
            while not self._kill_switch.isSet():
                # Connect
                result = self._client.connect()
                if result != 0:
                    self.status = result
                    break

                # Get the last key (end point for this script)
                result = self._client.blocking_cmd('get_previous', key="\xff"*self._client.sign_on_msg.body.getLog.limits.maxKeySize)
                if not result['success']:
                    self.status = 350
                    print cfg.StrFmt.Notice('[Errno 350] failed to get last key. '+cfg.StrFmt.ProtoStatus(result['cmd'].status))
                    self._client.status_dsm('[Errno 350] failed to get last key')
                    self._kill_switch.set()
                    break
                self.end_key = result['cmd'].body.keyValue.key

                print "End key: " + repr(self.end_key)

                # Break if kill switch is set
                if self._kill_switch.isSet():
                    break

                # Start performance tracker
                if not self._performanceTracker.is_running.isSet() and not self._kill_switch.isSet():
                    self._performanceTracker.start(self._reporting_interval)

                # Do the work
                try:
                    self._client.queue_depth = QUEUE_DEPTH
                    while self._client.is_connected and not self._kill_switch.isSet():
                        k = self.key_gen.get_next_key()
                        self._client.callback_delegate = self._client_callback(time.time(), k)
                        self._client.get(key=k)
                        op_count += 1
                        if op_count >= self._max_num_ops:
                            self._kill_switch.set()
                except KeyGeneratorException as e:
                    self.status = 312
                    print cfg.StrFmt.Notice('[Errno 312] '+str(e))
                    self._client.status_dsm('[Errno 312] failed key_gen.get_next()')
                    break
        except Exception as e:
            self.status = 300
            print cfg.StrFmt.Notice('[Errno 300] unknown exception. '+str(e))
            self._client.status_dsm('[Errno 300] unknown exception')

        # Call stop to do final clean up
        if not self._stop_called.isSet():
            self.stop(activity_call=True)
        print cfg.StrFmt.Notice(str(op_count)+" gets were issued")

    def _client_callback(self, t0, key):
        def wrapper(msg, cmd, value):
            # print "Callback: {} [{}]".format(repr(key), len(value))
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                if cmd.header.messageType == kinetic_pb2.Command.GET_RESPONSE:
                    load_size = len(cmd.body.keyValue.key)+len(value)
                    self._performanceTracker.log_op(latency=latency, value=load_size)
            else:
                if cmd.status.code == kinetic_pb2.Command.Status.NOT_FOUND and key >= self.end_key:
                    if not self._kill_switch.isSet():
                        self._kill_switch.set()
                        print cfg.StrFmt.Notice("response error (lat: "+str(latency)+\
                                                ") : "+cfg.StrFmt.ProtoStatus(cmd.status))
                else:
                    print cfg.StrFmt.Notice("response error (lat: "+str(latency)+\
                                            ") : "+cfg.StrFmt.ProtoStatus(cmd.status))
        return wrapper

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
    parser.add_argument("-r", "--reporting_interval", type=float, default=DEFAULT_REPORTING_INTERVAL,
                        help="How often (in seconds) would you like to report data")
    parser.add_argument("-k", "--key_gen", default=DEFAULT_KEY_GEN,
                        help="The path to a key generator config file")
    parser.add_argument("-o", "--max_num_ops", type=int, default=DEFAULT_MAX_NUM_OPS,
                        help="How many gets to perform before exiting, can be overidden through a stop command")
    args = parser.parse_args()

    gs = Gets(serial_number=args.serial_number,
              interface=args.interface,
              reporting_interval=args.reporting_interval,
              keygen_config=args.key_gen,
              max_num_ops=args.max_num_ops)

    if gs.status < 100:
        try:
            gs.start()
            gs.wait()
        except (KeyboardInterrupt, SystemExit):
            gs.stop()

    if gs.status >= 100:
        sys.exit(1)
