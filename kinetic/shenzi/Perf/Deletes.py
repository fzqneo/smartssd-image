"""
Deletes
Usage: python Deletes.py -s serial_number [-i interface] [-r reporting_interval in seconds]
                                       [-k key_gen config file]
Purpose: Will issue deletes until the drive is empty or the number of ops is completed.
         In addition to being accessed through command line, it's possible to import and create an
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
QUEUE_DEPTH = 1000
SYNCHRONIZATION = 1
FORCE = False
PERFORMANCE_TRACKER_HEADER = ['time_stamp',
                              'ipv4_addr',
                              'percent_full',
                              'resp_count_total',
                              'latency_ave',
                              'latency_max',
                              'latency_min']

DEFAULT_INTERFACE = None
DEFAULT_REPORTING_INTERVAL = 60
DEFAULT_KEY_GEN = os.path.join(SHENZI_PATH,"Support","Keys","FixedSequential")
DEFAULT_MAX_OPS = max
DEFAULT_BATCH_SIZE = None # Default is none, meaning commands are not batched

# -------------------------------------------------------------------------------------------------
# Deletes
# -------------------------------------------------------------------------------------------------
class Deletes(StartWaitStopPerfAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                 keygen_config=DEFAULT_KEY_GEN, max_num_ops=DEFAULT_MAX_OPS, batch_size=DEFAULT_BATCH_SIZE):
        # Initialize values
        super(Deletes, self).__init__(serial_number, interface, reporting_interval, keygen_config, max_num_ops, 'Deletes')
        self._performanceTracker.set_header(PERFORMANCE_TRACKER_HEADER)
        self._batch_size = batch_size
        if self._batch_size:
            self._issue_delete = self._batch_delete
            self._exit_status_code = kinetic_pb2.Command.Status.INVALID_BATCH
            self._success_msg_type = kinetic_pb2.Command.END_BATCH_RESPONSE
        else:
            self._issue_delete = self._delete
            self._exit_status_code = kinetic_pb2.Command.Status.NOT_FOUND
            self._success_msg_type = kinetic_pb2.Command.DELETE_RESPONSE

        # Print out the configuration details
        configuration = "interface: "+str(interface)
        configuration += ", reporting_interval: "+str(reporting_interval)
        if max_num_ops != DEFAULT_MAX_OPS:
            configuration += ", max_num_ops: "+str(max_num_ops)
        if batch_size:
            configuration += ", batch_size: "+str(batch_size)
        configuration += ", key.type: "+str(self.key_gen.type)
        for item in self.key_gen.original_specs:
            configuration += ", key."+item+": "+str(self.key_gen.original_specs[item])
        print cfg.StrFmt.Notice("Configuration", configuration)

        # Validate limits (key sizes and batch size)
        result = self._validate_limits(maxKeySize=self.key_gen.max_key_size, maxDeletesPerBatch=self._batch_size)
        if not result['success']:
            self.status = 310
            print cfg.StrFmt.Notice('[Errno 310] '+str(result['response']))
            self._client.status_dsm('[Errno 310] Failed limit validation')

    def stop(self, activity_call=False, last_call=True, verbose=True):
        """
        Override the stop method so data can be grabbed about the drive
        """
        super(Deletes, self).stop(activity_call=activity_call, last_call=False, verbose=verbose)

        print cfg.StrFmt.Notice("connecting client to get final data")
        result = self._client.connect()
        if result != 0:
            self.status = result
            self._stop_complete.set()
            return
        else:
            maxReturned = int(self._client.sign_on_msg.body.getLog.limits.maxKeyRangeCount)
            result = self._client.blocking_cmd("get_log", types=[2])
            if result['success']:
                portion_full = str(result['cmd'].body.getLog.capacity.portionFull)
                print cfg.StrFmt.Notice("portion full = "+portion_full)
            result = self._client.blocking_cmd('get_key_range',
                                                startKeyInclusive=True,
                                                endKeyInclusive=True,
                                                startKey='',
                                                maxReturned=maxReturned)
            if result['success']:
                key_count = str(len(result['cmd'].body.range.keys))
                print cfg.StrFmt.Notice("get_key_range returned "+key_count+" keys")
            self._client.close()
            self._stop_complete.set()

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
                        self._client.callback_delegate = self._client_callback(time.time())
                        op_count = self._issue_delete(op_count)
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
        print cfg.StrFmt.Notice(str(op_count)+" deletes were issued")

    def _delete(self, op_count):
        self._client.delete(key=self.key_gen.get_next_key(),
                                 synchronization=SYNCHRONIZATION,
                                 force=FORCE)
        return op_count+1

    def _batch_delete(self, op_count):
        batch_handle = self._client.create_batch_operation()
        for _ in range(self._batch_size):
            if op_count >= self._max_num_ops:
                break
            batch_handle.delete(key=self.key_gen.get_next_key(),
                                synchronization=SYNCHRONIZATION,
                                force=FORCE)
            op_count += 1
        batch_handle.commit()
        return op_count

    def _client_callback(self, t0):
        def wrapper(msg, cmd, value):
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                if cmd.header.messageType == self._success_msg_type:
                    self._performanceTracker.log_op(latency=latency)
            else:
                if cmd.status.code == self._exit_status_code:
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
    parser.add_argument("-b", "--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="How many deletes to put in a batch, if unspecified commands won't be batched")
    parser.add_argument("-o", "--max_num_ops", type=int, default=DEFAULT_MAX_OPS,
                        help="How many deletes to perform before exiting, can be overidden through a stop command")
    args = parser.parse_args()

    for name, value in [('reporting_interval', args.reporting_interval), ('max_num_ops', args.max_num_ops), ('batch_size', args.batch_size)]:
        if (value != None and value <= 0.0):
            parser.error('If you are going to specify '+name+', please specify a value greater than 0')

    ps = Deletes(serial_number=args.serial_number,
              keygen_config=args.key_gen,
              interface=args.interface,
              reporting_interval=args.reporting_interval,
              batch_size=args.batch_size,
              max_num_ops=args.max_num_ops)

    if ps.status < 100:
        try:
            ps.start()
            ps.wait()
        except (KeyboardInterrupt, SystemExit):
            ps.stop()

    if ps.status >= 100:
        sys.exit(1)
