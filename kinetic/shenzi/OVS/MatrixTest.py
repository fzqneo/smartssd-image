"""
Matrix Test for OVS
Usage: python MatrixTest.py -s serial_number [-i interface] [-r reporting_interval in seconds]
                            [-t test_interval in seconds] [--client_range] [--queue_range]
                            [--client_step_size] [--queue_step_size] [--load_count]
                            [--key_random_percent] [--first_put_force] [--key_no_prefix]
                            [--key_use_retired_random] [--report_max_lat] [--skip_version_check]
Purpose: Created to try and quage a 'best practice' for OVS workload
         Each subtest
            ISE
            OVS Batches with x number of clients, each with a queue depth of y
"""
import os
import sys
from argparse import ArgumentParser
from threading import Event, Thread
from Batches import Batches as BatchesOVS
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
from Cmd.ISE import ISE
from Support.ScriptBases import StartWaitStopAPI

# Globals -----------------------------------------------------------------------------------------
DEFAULT_CLIENT_RANGE = [1,40]
DEFAULT_QUEUE_RANGE = [1,40]
DEFAULT_CLIENT_STEP_SIZE = 1
DEFAULT_QUEUE_STEP_SIZE = 1

DEFAULT_INTERFACE = None
DEFAULT_REPORTING_INTERVAL = 60
DEFAULT_TEST_INTERVAL = 95

# -------------------------------------------------------------------------------------------------
# Master
# -------------------------------------------------------------------------------------------------
class MatrixTest(StartWaitStopAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, test_interval=DEFAULT_TEST_INTERVAL, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                 client_range=DEFAULT_CLIENT_RANGE, queue_range=DEFAULT_QUEUE_RANGE,
                 client_step_size=DEFAULT_CLIENT_STEP_SIZE, queue_step_size=DEFAULT_QUEUE_STEP_SIZE, **kwargs):
        self.serial_number = serial_number
        self.interface = interface
        self._test_interval = test_interval
        self._reporting_interval = reporting_interval
        self._client_range = client_range
        self._queue_range = queue_range
        self._client_step_size = client_step_size
        self._queue_step_size = queue_step_size
        self._ovs_kwargs = kwargs

        self._ise_script = ISE(self.serial_number, self.interface)
        self._ise_script.script_name = 'MatrixTest_ISE'
        self._current_batch = None
        super(MatrixTest, self).__init__('MatrixTest')

    def stop(self, activity_call=False):
        super(MatrixTest, self).stop(activity_call)
        if self._current_batch != None:
            self._current_batch.stop()
        self._ise_script.wait()

    def _activity(self):
        self._run_test()
        self.stop(activity_call=True)

    def _run_test(self):
        for q_index, queue_depth in enumerate(range(self._queue_range[0], self._queue_range[1]+1)):
            for c_index, client_count in enumerate(range(self._client_range[0], self._client_range[1]+1)):
                if self._kill_switch.is_set():
                    return

                if q_index%self._queue_step_size != 0 or c_index%self._client_step_size != 0:
                    continue

                print "".ljust(100, '-'),"\nClients: ",client_count," | Queue Depth: ",queue_depth,"\n","".ljust(100, '-')
                self._ise_script.start()
                self._ise_script.wait()

                if self._ise_script.status >= 100:
                    continue

                if self._kill_switch.is_set():
                    return

                self._current_batch = BatchesOVS(serial_number=self.serial_number,
                                                 interface=self.interface,
                                                 reporting_interval=self._reporting_interval,
                                                 num_client_connections=client_count,
                                                 batch_queue=queue_depth,
                                                 script_name='MatrixTest_BatchesOVS_C:'+str(client_count)+'_Q:'+str(queue_depth),
                                                 **self._ovs_kwargs)
                self._current_batch.start()
                self._current_batch.wait(self._test_interval, terminate=True)

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__=="__main__":
    # Parse Input
    parser = ArgumentParser()
    parser.add_argument("-s", "--serial_number", required=True,
                        help="The serial number of the drive to test on")
    parser.add_argument("-i", "--interface",
                        help="The interface on the drive to test on")
    parser.add_argument("-t", "--test_interval", type=float,
                        help="How long (in seconds) would you like to run the test for each cell")
    parser.add_argument("-r", "--reporting_interval", type=float,
                        help="How often (in seconds) would you like to report data")
    parser.add_argument("-c", "--client_range", type=int, nargs=2,
                        help="Takes 2 ints reflecting the number of client subtests to run, default is 1-40")
    parser.add_argument("-q", "--queue_range", type=int, nargs=2,
                        help="Takes 2 ints reflecting the number of que-depth subtests to run, default is 1-40")
    parser.add_argument("-qs", "--queue_step_size", type=int,
                        help="What step size to use on queue range subtests, default is 1")
    parser.add_argument("-cs", "--client_step_size", type=int,
                        help="What step size to use on client range subtests, default is 1")

    # These parameters were added for additional OVS Batch test
    parser.add_argument("-k", "--key_gen",
                        help="The path to a key generator config file")
    parser.add_argument("--load_count", type=int,
                        help="How many OVS work loads to stuff into a batch")
    parser.add_argument("--first_put_force", action="store_true",
                        help="Force flag will be set true on first put in each load")
    parser.add_argument("--key_no_prefix", action="store_true",
                        help="Do not attach a prefix to keys")
    parser.add_argument("--report_max_lat", action="store_true",
                        help="Reports max latency per connection instead of percent contribution")
    parser.add_argument("--skip_version_check", action="store_true",
                        help="Skip the version check on first put in each load")
    parser.add_argument("--flush_every_batch", action="store_true",
                        help="Will set synchronization field to flush for every batch commit")
    parser.add_argument("--random_seed", type=int,
                        help="will set the random seed that decides prefixes and key patterns for all clients")
    args = parser.parse_args()

    # Remove any inputs that were not populated
    remove_items = [item for item in vars(args) if (not getattr(args,item) and not (type(getattr(args,item)) == float or type(getattr(args,item)) == int))]
    for item in remove_items:
        delattr(args,item)

    try:
        matrix = MatrixTest(**vars(args))
        matrix.start()
        matrix.wait()
    except (KeyboardInterrupt, SystemExit):
        matrix.stop()
