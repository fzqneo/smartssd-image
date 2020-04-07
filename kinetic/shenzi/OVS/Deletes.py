"""
Deletes for OVS
Usage: python Deletes.py -s serial_number [-i interface] [-n number of keys to delete]

Purpose: Special script for OpenVStore workload testing
"""
import os
import sys
import time
from argparse import ArgumentParser
from collections import defaultdict
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
RESULTS_PATH = os.path.join(SHENZI_PATH,"Mine","Results")
sys.path.insert(0,SHENZI_PATH)
import Mine.Config as cfg
from Support.ShenziClient import kinetic_pb2
from Support.ScriptBases import StartWaitStopClientAPI
from Support.PerformanceTracker import PerformanceTracker

# Globals -----------------------------------------------------------------------------------------
DEFAULT_INTERFACE = None
DEFAULT_MAX_NUM_OPS = max

SYNCHRONIZATION = 1
DEFAULT_REPORTING_INTERVAL = 60
PERFORMANCE_TRACKER_HEADER = ['time_stamp',
                              'ipv4_addr',
                              'percent_full',
                              'resp_count_total',
                              'latency_ave',
                              'latency_max',
                              'latency_min']

DEFAULT_MAX_LATENCY = 10 # if latency is greater than or equal to this number, it will trigger a get log and stop the test

# -------------------------------------------------------------------------------------------------
# Deletes
# -------------------------------------------------------------------------------------------------
class Deletes(StartWaitStopClientAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                    max_num_ops=DEFAULT_MAX_NUM_OPS, max_latency=DEFAULT_MAX_LATENCY):
        # Initialize values
        super(Deletes, self).__init__(serial_number, interface, 'Deletes')
        self._performanceTracker = PerformanceTracker(serial_number, interface)
        self._performanceTracker.set_header(PERFORMANCE_TRACKER_HEADER)
        self._max_num_ops = max_num_ops
        self._max_latency = max_latency
        self._reporting_interval = reporting_interval
        self._batch_lat = None

        # Print out the configuration details
        configuration = "interface: "+str(interface)+\
                        ", reporting_interval: "+str(reporting_interval)+\
                        ", max_latency: "+str(max_latency)
        if max_num_ops != max:
            configuration += ", max_num_ops: "+str(max_num_ops)
        print cfg.StrFmt.Notice("Configuration", configuration)

    # Activity thread -----------------------------------------------------------------------------
    def _activity(self):
        try:
            delete_count = 0
            get_key_range_count = 0
            self._client.connect()
            self._performanceTracker.start(self._reporting_interval)
            # Keep trying until kill switch is set or a failure in setup
            while not self._kill_switch.isSet():

                # Connect
                if not self._client.is_connected:
                    result = self._client.connect()
                    if result != 0:
                        self.status = result
                        return
                if self._kill_switch.isSet():
                    return

                # Issue GetKeyRange
                response = self._client.blocking_cmd('get_key_range',
                                                      startKeyInclusive=True,
                                                      endKeyInclusive=True,
                                                      startKey='',
                                                      maxReturned=self._client.sign_on_msg.body.getLog.limits.maxKeyRangeCount)
                if not response['success']:
                    print cfg.StrFmt.Notice("Failed get_key_range command | "+cfg.StrFmt.ProtoStatus(response['cmd'].status))
                    return
                get_key_range_count += 1
                if len(response['cmd'].body.range.keys) == 0:
                    print cfg.StrFmt.Notice("get_key_range returned empty key list")
                    return
                if self._kill_switch.isSet():
                    return

                # Issue deletes
                error_resp = defaultdict(int)
                self._client.callback_delegate = self._client_callback(time.time(), error_resp)
                batch_handle = self._client.create_batch_operation()
                for key in response['cmd'].body.range.keys:
                    batch_handle.delete(key=key,synchronization=SYNCHRONIZATION)
                    delete_count += 1
                    if delete_count >= self._max_num_ops:
                        self._kill_switch.set()
                        break
                batch_handle.commit()
                self._client.wait_q(0)

                # Check for large latency
                if self._batch_lat > self._max_latency:
                    file_name = time.strftime('%Y-%m-%d_%H-%M-%S')+"_"+self._client.serial_number+"_"+self.script_name+"_GetLogMessages.txt"
                    file_name = os.path.join(RESULTS_PATH, file_name)
                    print cfg.StrFmt.Notice("Recieved latency of "+str(self._batch_lat)+"s, writing getlog to "+file_name)
                    getlog_result = self._client.blocking_cmd('get_log', types=[5])
                    with open(file_name, 'w') as file_handle:
                        if getlog_result['success']:
                            file_handle.write(getlog_result['cmd'].body.getLog.messages)
                        else:
                            file_handle.write(str(getlog_result))
                    return

                # Check for successful responses
                if len(error_resp) != 0:
                    print cfg.StrFmt.Notice("Failed batch delete | "+str(error_resp))
                    return

        except Exception as e:
            self.status = 300
            print cfg.StrFmt.Notice('[Errno 300] unknown exception. '+str(e))
            self._client.status_dsm('[Errno 300] unknown exception')
        finally:
            # Call stop to do final clean up
            self._performanceTracker.stop()
            if not self._stop_called.isSet():
                self.stop(activity_call=True)
            print cfg.StrFmt.Notice('Number of Get Key Ranges issued: '+str(get_key_range_count))

    def _client_callback(self, t0, errors):
        def wrapper(msg, cmd, value):
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                if cmd.header.messageType == kinetic_pb2.Command.END_BATCH_RESPONSE:
                    self._batch_lat = latency
                    self._performanceTracker.log_op(latency=self._batch_lat)
            else:
                errors[cfg.StrFmt.ProtoStatus(cmd.status)] += 1
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
    parser.add_argument("-o", "--max_num_ops", type=int, default=DEFAULT_MAX_NUM_OPS,
                        help="How many deletes to perform before exiting, can be overidden through a stop command")
    parser.add_argument("-l","--max_latency", type=float, default=DEFAULT_MAX_LATENCY,
                        help="If a batch delete has a latency higher than this, print out a notice, and issue a getlog 5 (write output to results file)")
    args = parser.parse_args()

    dlts = Deletes(serial_number=args.serial_number,
                      interface=args.interface,
                      reporting_interval=args.reporting_interval,
                      max_num_ops=args.max_num_ops,
                      max_latency=args.max_latency)
    if dlts.status < 100:
        try:
            dlts.start()
            dlts.wait()
        except (KeyboardInterrupt, SystemExit):
            dlts.stop()

    if dlts.status >= 100:
        sys.exit(1)

