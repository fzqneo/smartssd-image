"""
Puts
Usage: python Puts.py -s serial_number [-i interface] [-r reporting_interval in seconds]
                                       [-k key_gen config file] [-v value_size]
Purpose: Will issue puts until a put fails for the drive being full.
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
QUEUE_DEPTH = 250
SYNCHRONIZATION = 1
FORCE = True

DEFAULT_INTERFACE = None
DEFAULT_REPORTING_INTERVAL = 60
DEFAULT_VALUE_SIZE = 1024*1024
DEFAULT_KEY_GEN = os.path.join(SHENZI_PATH,"Support","Keys","FixedSequential")
DEFAULT_MAX_NUM_OPS = max
DEFAULT_BATCH_SIZE = None # Default is none, meaning commands are not batched

# -------------------------------------------------------------------------------------------------
# Puts
# -------------------------------------------------------------------------------------------------
class Puts(StartWaitStopPerfAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                 keygen_config=DEFAULT_KEY_GEN, value_size=DEFAULT_VALUE_SIZE, batch_size=DEFAULT_BATCH_SIZE,
                 max_num_ops=DEFAULT_MAX_NUM_OPS):
        # Initialize values
        super(Puts, self).__init__(serial_number, interface, reporting_interval, keygen_config, max_num_ops, 'Puts')
        self.value = "\xff"*value_size
        self._batch_size = batch_size
        if self._batch_size:
            self._issue_put = self._batch_put
            test_max_batch_size = (self.key_gen.max_key_size+value_size)*batch_size
        else:
            self._issue_put = self._put
            test_max_batch_size = None

        # Print out the configuration details
        configuration = "interface: "+str(interface)
        configuration += ", reporting_interval: "+str(reporting_interval)
        configuration += ", value_size: "+str(value_size)
        if max_num_ops != DEFAULT_MAX_NUM_OPS:
            configuration += ", max_num_ops: "+str(max_num_ops)
        if batch_size:
            configuration += ", batch_size: "+str(batch_size)
        configuration += ", key.type: "+str(self.key_gen.type)
        for item in self.key_gen.original_specs:
            configuration += ", key."+item+": "+str(self.key_gen.original_specs[item])
        print cfg.StrFmt.Notice("Configuration", configuration)

        # Validate limits (key sizes and batch size)
        result = self._validate_limits(maxKeySize=self.key_gen.max_key_size, maxValueSize=value_size,
                                       maxBatchSize=test_max_batch_size)
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
                            op_count = self._issue_put(op_count)
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
        print cfg.StrFmt.Notice(str(op_count)+" puts were issued")

    def _put(self, op_count):
        self._client.put(key=self.key_gen.get_next_key(),
                              value=self.value,
                              synchronization=SYNCHRONIZATION,
                              force=FORCE)
        return op_count+1

    def _batch_put(self, op_count):
        batch_handle = self._client.create_batch_operation()
        for _ in range(self._batch_size):
            if op_count >= self._max_num_ops:
                break
            batch_handle.put(key=self.key_gen.get_next_key(),
                             value=self.value,
                             synchronization=SYNCHRONIZATION,
                             force=FORCE)
            op_count += 1
        batch_handle.commit()
        return op_count

    def _client_callback(self, t0):
        def wrapper(msg, cmd, value):
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                load_size = 0
                log_perf = False
                if cmd.header.messageType == kinetic_pb2.Command.PUT_RESPONSE:
                    load_size = self.key_gen.max_key_size+len(self.value)
                    log_perf = True
                elif cmd.header.messageType == kinetic_pb2.Command.END_BATCH_RESPONSE:
                    load_size = (self.key_gen.max_key_size+len(self.value))*self._batch_size
                    log_perf = True
                if log_perf:
                    self._performanceTracker.log_op(latency=latency, value=load_size)
            else:
                if cmd.status.code == kinetic_pb2.Command.Status.NO_SPACE:
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
    parser.add_argument("-v", "--value_size", type=int, default=DEFAULT_VALUE_SIZE,
                        help="How many bytes should the values be, default is 1MiB")
    parser.add_argument("-b", "--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="How many puts to put in a batch, if unspecified commands won't be batched")
    parser.add_argument("-o", "--max_num_ops", type=int, default=DEFAULT_MAX_NUM_OPS,
                        help="How many puts to perform before exiting, can be overidden through a stop command")
    args = parser.parse_args()

    for name, value in [('reporting_interval', args.reporting_interval), ('max_num_ops', args.max_num_ops), ('batch_size', args.batch_size)]:
        if (value != None and value <= 0.0):
            parser.error('If you are going to specify '+name+', please specify a value greater than 0')

    ps = Puts(serial_number=args.serial_number,
              keygen_config=args.key_gen,
              value_size=args.value_size,
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
