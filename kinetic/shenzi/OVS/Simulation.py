"""
OVS Client simulation
"""
import os
import sys
import time
import random
from argparse import ArgumentParser
from threading import Event, Thread, Lock
SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
RESULTS_PATH = os.path.join(SHENZI_PATH,"Mine","Results")
sys.path.insert(0,SHENZI_PATH)
import Mine.Config as cfg
import Support.KeyGenerator as KeyGen
from Support.ShenziClient import ShenziClient, kinetic_pb2
from Support.General import get_drive_list_input

# Globals -----------------------------------------------------------------------------------------
OVS_WORKLOAD = ["", "\xff"*1024*1024, "\xff"*140]

KEY_SPECIFIER = {"random_percentage":1.0,
                 #"use_retired_random":True,
                 "key_size":100}

# -------------------------------------------------------------------------------------------------
# OVS Client
# -------------------------------------------------------------------------------------------------
class OVSClient(object):
    def __init__(self, identity, random_seed, kill_switch, serial_number_list):
        self._key_gen = KeyGen.create_keygen("fixed")(dict({'random_seed':random_seed}, **KEY_SPECIFIER))
        self._perf_data_lock = Lock()
        self._batch_group_lock = Lock()
        self._completed_batch_group = Event()
        self._current_batch_group = 0
        self._success_response_count = 0
        self._clients = [ShenziClient(drive) for drive in serial_number_list]

        self.id = str(identity)
        self.key_prefix = str(random_seed).rjust(self._key_gen.key_size,'\x00')[-self._key_gen.key_size:]
        self.kill_switch = kill_switch

    def format_output(self, msg):
        return cfg.StrFmt.Notice("OVS_Client_"+str(self.id), str(msg))

    def run(self, num_ops, load_count, performance_data, num_success, full_lat):
        # Setup
        self._tx_bytes = 0
        self.load_count = load_count
        self._num_success = num_success
        self._current_batch_group = 0
        if full_lat:
            self._latency_data = {c.serial_number:[] for c in self._clients}
        else:
            self._latency_data = {c.serial_number:{'sum':0, 'count':0, 'max':None, 'min':''} for c in self._clients}
        for client in self._clients:
            client.queue_depth = num_ops
        self.load_size = sum([len(v)+self._key_gen.key_size+len(self.key_prefix) for v in OVS_WORKLOAD])*self.load_count

        # Issue all batch groups
        t0 = time.time()
        for _ in range(num_ops):
            if self.kill_switch.isSet():
                break
            with self._batch_group_lock:
                self._current_batch_group += 1
                self._success_response_count = 0
                self._completed_batch_group.clear()
            keys = [(self.key_prefix+self._key_gen.get_next_key()) for _ in range(self.load_count*len(OVS_WORKLOAD))]
            self._issue_batch_to_all_drives(keys)
            self._completed_batch_group.wait(31556926)
        # Wait for all outstanding responses
        for client in self._clients:
            client.wait_q(0)
            client.close()
        t1 = time.time()
        performance_data[self.id] = {'latency':self._latency_data, 'tx_bytes':self._tx_bytes, 'time_span':(t1-t0)}

    def connect_all_clients(self):
        threads = [Thread(target=c.connect) for c in self._clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def is_connected(self):
        connected = [c.is_connected for c in self._clients]
        return bool(connected.count(False) == 0)

    def _issue_batch_to_all_drives(self, keys):
        threads = [Thread(target=self._issue_batch_cmd, args=(c, list(keys))) for c in self._clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _issue_batch_cmd(self, client, keys):
        client.callback_delegate = self._client_callback(client.serial_number,
                                                         time.time(),
                                                         self._current_batch_group)
        batch_handle = client.create_batch_operation()
        while len(keys) >= len(OVS_WORKLOAD):
            batch_handle.put(key=keys.pop(),
                             value=OVS_WORKLOAD[0],
                             version="",
                             force=False,
                             synchronization=1)
            for value in OVS_WORKLOAD[1:]:
                batch_handle.put(key=keys.pop(),
                                 value=value,
                                 force=True,
                                 synchronization=1)
        batch_handle.commit()

    def _log_performance(self, serial_number, latency, load=0):
        with self._perf_data_lock:
            if type(self._latency_data[serial_number]) == list:
                self._latency_data[serial_number].append(latency)
            else:
                self._latency_data[serial_number]['count'] += 1
                self._latency_data[serial_number]['sum'] += latency
                self._latency_data[serial_number]['max'] = max(latency, self._latency_data[serial_number]['max'])
                self._latency_data[serial_number]['min'] = min(latency, self._latency_data[serial_number]['min'])
            self._tx_bytes += load

    # Client command callbacks --------------------------------------------------------------------
    def _client_callback(self, serial_number, t0, batch_group):
        def wrapper(msg, cmd, value):
            latency = time.time() - t0
            if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
                if cmd.header.messageType ==  kinetic_pb2.Command.END_BATCH_RESPONSE:
                    self._log_performance(serial_number, latency, load=self.load_size)
                    with self._batch_group_lock:
                        if batch_group == self._current_batch_group:
                            self._success_response_count += 1
                            if self._success_response_count >= self._num_success:
                                self._completed_batch_group.set()
            else:
                self.kill_switch.set()
                print self.format_output("serial_number: "+serial_number+\
                                         " | response error (lat: "+str(latency)+\
                                         ") : "+cfg.StrFmt.ProtoStatus(cmd.status))
        return wrapper

# -------------------------------------------------------------------------------------------------
# OVS Client Manager
# -------------------------------------------------------------------------------------------------
class OVSClientManager(object):
    def __init__(self):
        self.random_seed = int(time.time())
        self._kill_switch = Event()

    def format_output(self, msg):
        return cfg.StrFmt.Notice("OVS_Client_Manager", str(msg))

    def run(self, num_clients, serial_number_list, num_ops, load_count, num_success, full_lat):
        print self.format_output("creating ovs clients")
        ovs_clients = random.Random(self.random_seed).sample(range(0,9999), num_clients)
        ovs_clients = [OVSClient(i, j, self._kill_switch, serial_number_list) for i, j in enumerate(ovs_clients)]
        performance_data = {str(i):None for i in range(len(ovs_clients))}

        print self.format_output("connecting all kinetic clients for all ovs clients")
        threads = [Thread(target=ovs_client.connect_all_clients) for ovs_client in ovs_clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        failed_connections = [ovs_client.is_connected() for ovs_client in ovs_clients].count(False)
        if failed_connections != 0:
            print self.format_output(str(failed_connections)+" ovs clients failed to connect all their clients")
            return {}

        print self.format_output("starting ovs clients")
        threads = [Thread(target=ovs_client.run, args=(num_ops, load_count, performance_data, num_success, full_lat)) for ovs_client in ovs_clients]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        print self.format_output("finished testing")
        return performance_data

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
def main():
    parser = ArgumentParser()

    drive_list, _ = get_drive_list_input()
    if not drive_list:
        parser.error("please pipe in a drive list to work on")

    parser.add_argument("-o", "--ovs_clients", required=True, type=int,
                        help="how many OVS clients to run")
    parser.add_argument("-n", "--num_ops", required=True, type=int,
                        help="How many operations each OVS will issue before finishing")
    parser.add_argument("-l", "--load_count", required=True, type=int,
                        help="How many OVS loads within each batch")
    parser.add_argument("--num_success", type=int, default=len(drive_list),
                        help="How many successful responses each OVS client needs to continue on. This number must be [0,number of drives]")
    parser.add_argument("--full_lat", action="store_true",
                        help="report all latency data")
    args = parser.parse_args()
    if args.num_success < 0 or args.num_success > len(drive_list):
        parser.error("num_success must be greater-than zero and less-than or equal to number of drives")

    ovsClientMgr = OVSClientManager()
    perf_data = ovsClientMgr.run(args.ovs_clients, drive_list, args.num_ops, args.load_count, args.num_success, args.full_lat)
    if perf_data:
        file_lines = ["ovs_client_id,serial_number,latency"]
        print "Aggregate throughput of OVS Clients: "+str(sum([((float(perf_data[i]['tx_bytes'])/perf_data[i]['time_span'])*.000001) for i in perf_data]))
        for i in sorted(perf_data):
            print "OVS Client "+str(i)+":\n\tthroughput(MB/s): "+str((float(perf_data[i]['tx_bytes'])/perf_data[i]['time_span'])*.000001)
            print "\tlatency (s):"
            for drive in sorted(perf_data[i]['latency']):
                if type(perf_data[i]['latency'][drive]) == list:
                    print "\t\tlook at output file"
                    file_lines.append(str(i)+","+str(drive)+","+",".join([str(l) for l in perf_data[i]['latency'][drive]]))
                else:
                    print "\t\t"+str(drive)+":"
                    print "\t\t\tmax: "+str(perf_data[i]['latency'][drive]['max'])
                    print "\t\t\tmin: "+str(perf_data[i]['latency'][drive]['min'])
                    if perf_data[i]['latency'][drive]['count'] == 0:
                        print "ave: None"
                    else:
                        print "\t\t\tave: "+str(float(perf_data[i]['latency'][drive]['sum'])/perf_data[i]['latency'][drive]['count'])
        if len(file_lines) > 1:
            output_file = os.path.join(RESULTS_PATH,(time.strftime('%Y-%m-%d_%H-%M-%S')+"_OVSSimulationLatencies.csv"))
            print "Latency data can be found here: "+str(output_file)
            with open(output_file, 'w') as f:
                for line in file_lines:
                    f.write(line+"\n")

if __name__=="__main__":
    main()
