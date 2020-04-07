"""
Batches for OVS
Usage: python Batches.py -s serial_number [-i interface] [-r reporting_interval in seconds]
                         [-c num_client_connections] [-q batch_queue] [--load_count]
                         [--key_random_percent] [--first_put_force] [--key_no_prefix]
                         [--key_use_retired_random] [--report_max_lat] [--skip_version_check]
Purpose: Special script for OpenVStore workload testing
"""
import os
import sys
import time
import random
from threading import Thread
from argparse import ArgumentParser
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
sys.path.insert(0,SHENZI_PATH)
import Mine.Config as cfg
import Support.KeyGenerator as KeyGen
from Support.ShenziClient import ShenziClient, kinetic_pb2
from Support.ScriptBases import StartWaitStopClientAPI
from Support.PerformanceTracker import MultiClientPerformanceTracker

# Globals -----------------------------------------------------------------------------------------
# Key size should be half of the desired size because generated keys will be appended to a prefix of equal size
OVS_WORKLOAD = ["", "\xff"*1024*1024, "\xff"*140]

DEFAULT_INTERFACE = None
DEFAULT_REPORTING_INTERVAL = 60
DEFAULT_BATCH_QUEUE = 200
DEFAULT_NUM_CLIENTS = 1
DEFAULT_KEY_GEN = os.path.join(SHENZI_PATH,"OVS","Keys","Standard")

DEFAULT_LOAD_COUNT = 1
DEFAULT_KEY_NO_PREFIX = False
DEFAULT_REPORT_MAX_LAT = False
DEFAULT_FIRST_PUT_FORCE = False
DEFAULT_SKIP_VERSION_CHECK = False
DEFAULT_FLUSH_EVERY_BATCH = False
DEFAULT_RANDOM_SEED = None # None indicates to use a time stamp as the random seed

# -------------------------------------------------------------------------------------------------
# Worker
# -------------------------------------------------------------------------------------------------
class BatchOVSWorker(StartWaitStopClientAPI):
    def __init__(self, serial_number, interface, clientID, batch_queue, key_type, key_specifier, performance_log,
                death_signal, first_put_force, key_no_prefix, load_count, skip_version_check, flush_every_batch):
        self.clientID = str(clientID)
        super(BatchOVSWorker, self).__init__(serial_number, interface,'BatchWorker_'+self.clientID)
        self._client.verbosity = 0
        self._death_signal = death_signal
        self._performance_log = performance_log

        self._key_gen = KeyGen.create_keygen(key_type)(key_specifier)
        if key_no_prefix:
            self.key_prefix = ""
        else:
            self.key_prefix = str(self._key_gen.random_seed).rjust(self._key_gen.key_size,'\x00')[-self._key_gen.key_size:]
        self.load_count = load_count
        self.first_put_force = first_put_force
        self.skip_version_check = skip_version_check
        self.flush_every_batch = flush_every_batch
        self.batch_queue = batch_queue
        self.load_size = sum([len(v)+self._key_gen.key_size+len(self.key_prefix) for v in OVS_WORKLOAD])*self.load_count

    def start(self):
        super(BatchOVSWorker, self).start(verbose=False)

    def stop(self, activity_call=False):
        self._kill_switch.set()
        if self._stop_called.isSet():
            if not activity_call:
                self._stop_complete.wait()
            return
        self._stop_called.set()
        if activity_call:
            print cfg.StrFmt.Notice('ClientID: '+str(self.clientID)+' | activity stopped')
        else:
            print cfg.StrFmt.Notice('ClientID: '+str(self.clientID)+' | stop called')
        super(BatchOVSWorker, self).stop(activity_call=activity_call, verbose=False, last_call=False)
        self._death_signal()
        self._stop_complete.set()

    def connect_client(self):
        results = self._client.connect()
        if results == 0:
            return True
        else:
            self.status = results
            return False

    def is_connected(self):
        return self._client.is_connected

    def _activity(self):
        # Run Batches
        self._client.queue_depth = (self.batch_queue*2)
        while self._client.is_connected and not self._kill_switch.isSet():
            self._client.callback_delegate = self._worker_callback(time.time())
            batch_handle = self._client.create_batch_operation()
            for x in range(self.load_count):
                if self.skip_version_check:
                    batch_handle.put(key=self.key_prefix + self._key_gen.get_next_key(),
                                        value=OVS_WORKLOAD[0],
                                        force=self.first_put_force,
                                        synchronization=1)
                else:
                    batch_handle.put(key=self.key_prefix + self._key_gen.get_next_key(),
                                        value=OVS_WORKLOAD[0],
                                        version="",
                                        force=self.first_put_force,
                                        synchronization=1)
                for value in OVS_WORKLOAD[1:]:
                    batch_handle.put(key=self.key_prefix + self._key_gen.get_next_key(),
                                        value=value,
                                        force=True,
                                        synchronization=1)
            batch_handle.commit()
            if self.flush_every_batch:
                self._client.flush_all_data()
            self._client.wait_q(outstanding=(self.batch_queue-1))
        self.stop(activity_call=True)

    def _worker_callback(self, t0):
        def wrapper(msg, cmd, value):
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                if cmd.header.messageType == kinetic_pb2.Command.END_BATCH_RESPONSE:
                    self._performance_log(self.clientID, latency=latency, value=self.load_size)
            else:
                if cmd.status.code == kinetic_pb2.Command.Status.NO_SPACE:
                    if not self._kill_switch.is_set():
                        self._kill_switch.set()
                        print cfg.StrFmt.Notice("ClientID: "+self.clientID+\
                                                " | response error (lat: "+str(latency)+\
                                                ") : "+cfg.StrFmt.ProtoStatus(cmd.status))
                else:
                    print cfg.StrFmt.Notice("ClientID: "+self.clientID+\
                                            " | response error (lat: "+str(latency)+\
                                            ") : "+cfg.StrFmt.ProtoStatus(cmd.status))
        return wrapper

# -------------------------------------------------------------------------------------------------
# Master
# -------------------------------------------------------------------------------------------------
class Batches(StartWaitStopClientAPI):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE, reporting_interval=DEFAULT_REPORTING_INTERVAL,
                 key_gen=DEFAULT_KEY_GEN, num_client_connections=DEFAULT_NUM_CLIENTS, batch_queue=DEFAULT_BATCH_QUEUE,
                 script_name='OVSBatches', first_put_force=DEFAULT_FIRST_PUT_FORCE, key_no_prefix=DEFAULT_KEY_NO_PREFIX,
                 load_count=DEFAULT_LOAD_COUNT, report_max_lat=DEFAULT_REPORT_MAX_LAT,
                 skip_version_check=DEFAULT_SKIP_VERSION_CHECK, flush_every_batch=DEFAULT_FLUSH_EVERY_BATCH,
                 random_seed=DEFAULT_RANDOM_SEED):

        super(Batches, self).__init__(serial_number, interface, script_name)

        if random_seed == None:
            random_seed = int(time.time())
        self.reporting_interval = reporting_interval
        self._PerfTracker = MultiClientPerformanceTracker(serial_number=serial_number, interface=interface,
                                                          num_clients=num_client_connections, queue_depth=batch_queue,
                                                          report_max_lat=report_max_lat)
        key_type, key_specifier = KeyGen.parse_config_file(key_gen)
        if 'random_seed' in key_specifier:
            del key_specifier['random_seed']
        # Print out the configuration details
        config_details = "interface: " + str(interface) + \
                         ", reporting_interval: " + str(reporting_interval) + \
                         ", num_clients: " + str(num_client_connections) + \
                         ", batch_queue: " + str(batch_queue) + \
                         ", random_seed: " + str(random_seed)
        if first_put_force:
            config_details += ", first_put_force"
        if key_no_prefix:
            config_details += ", key_no_prefix"
        if report_max_lat:
            config_details += ", report_max_lat"
        if skip_version_check:
            config_details += ", skip_version_check"
        if flush_every_batch:
            config_details += ", flush_every_batch"
        if load_count != DEFAULT_LOAD_COUNT:
            config_details += ", load_count: "+str(load_count)
        config_details += ", key.type: "+str(key_type)
        for item in key_specifier:
            if item == 'key_size':
                config_details += ", key."+item+": "+str(int(key_specifier[item])*2)
            else:
                config_details += ", key."+item+": "+str(key_specifier[item])
        print cfg.StrFmt.Notice("Configuration", config_details)

        # Initialize workers with unique random key prefixes
        self.connections = random.Random(random_seed).sample(range(0,(10*int(key_specifier['key_size']))-1), num_client_connections)
        for index, unique_seed in enumerate(self.connections):
            i_key_specifier = (dict({'random_seed':unique_seed}, **key_specifier))
            self.connections[index] = BatchOVSWorker(serial_number=serial_number,
                                                  interface=interface,
                                                  clientID=index,
                                                  batch_queue=batch_queue,
                                                  key_type=key_type,
                                                  key_specifier=i_key_specifier,
                                                  performance_log=self._PerfTracker.log_op,
                                                  death_signal=self._client_death_call,
                                                  first_put_force=first_put_force,
                                                  key_no_prefix=key_no_prefix,
                                                  load_count=load_count,
                                                  skip_version_check=skip_version_check,
                                                  flush_every_batch=flush_every_batch)

    def start(self):
        self._client.status_dsm('starting '+self.script_name)
        super(Batches, self).start(verbose=False)

    def stop(self):
        self._kill_switch.set()
        if self._stop_called.isSet():
            self._stop_complete.wait()
            return
        self._stop_called.set()
        print cfg.StrFmt.Notice('stopping '+self.script_name)
        self._client.status_dsm('stopping '+self.script_name)
        self._PerfTracker.stop()
        self._stop_workers()
        if self.status < 100:
            self.status = 0
        print cfg.StrFmt.Notice('stopped '+self.script_name)
        self._client.status_dsm('stopped '+self.script_name)
        self._stop_complete.set()

    def _activity(self):
        print cfg.StrFmt.Notice('connecting all clients')
        failure_count = self._connect_workers()
        if failure_count > 0:
            print cfg.StrFmt.Notice('[Errno 370] failed to connect '+str(failure_count)+' clients')
            self.status = 370
            self.stop()
        else:
            print cfg.StrFmt.Notice('kineticd version: '+self.connections[0]._client.sign_on_msg.body.getLog.configuration.version)
            self._PerfTracker.start(self.reporting_interval)
            self._start_workers()
            self._kill_switch.wait(31556926)
            self.stop()

    def _client_death_call(self):
        self._kill_switch.set()

    def _connect_workers(self):
        threads = [Thread(target=connection.connect_client) for connection in self.connections]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return [connection.is_connected() for connection in self.connections].count(False)

    def _start_workers(self):
        threads = [Thread(target=connection.start) for connection in self.connections]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _stop_workers(self):
        threads = [Thread(target=connection.stop) for connection in self.connections]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

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
    parser.add_argument("-r", "--reporting_interval", type=float,
                        help="How often (in seconds) would you like to report data")
    parser.add_argument("-c", "--num_client_connections", type=int,
                        help="How many clients should run this workload at once")
    parser.add_argument("-q", "--batch_queue", type=int,
                        help="How many outstanding batch commands each client can have")
    parser.add_argument("-k", "--key_gen",
                        help="The path to a key generator config file")


    # These parameters were added for additional test
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
        bsOVS = Batches(**vars(args))
        bsOVS.start()
        bsOVS.wait()
    except (KeyboardInterrupt, SystemExit):
        bsOVS.stop()

    if bsOVS.status >= 100:
        sys.exit(1)