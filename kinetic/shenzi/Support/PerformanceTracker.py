"""
Performance Tracker
Usage: N/A
Purpose: Will report performance on any ShenziClient as long as the log_op method is
         incorporated in the owning script. Performance Tracker is a time-based reporting.
"""
import os
import sys
import time
import datetime
from threading import Thread, Event, Lock
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
from Support.ShenziClient import ShenziClient

# Globals -----------------------------------------------------------------------------------------
HEADER = ['time_stamp',
          'serial_number',
          'ipv4_addr',
          'percent_full',
          'cpu_temp',
          'hda_temp',
          'resp_count_total',
          'bytes_xfer',
          'bytes_xfer_total',
          'latency_ave',
          'latency_max',
          'latency_min',
          'MB/s']

MULTI_CLIENT_HEADER = ['time_stamp',
                       'serial_number',
                       'queue_depth',
                       'num_connections',
                       'percent_full',
                       'cpu_temp',
                       'hda_temp',
                       'bytes_xfer_total',
                       'latency_ave',
                       'latency_max',
                       'latency_min',
                       'MB/s']

GET_LOG_TIMEOUT = 30000 #timeouts sent to the drive are in milliseconds
DEFAULT_INTERFACE = None

# -------------------------------------------------------------------------------------------------
# Performance Tracker
# -------------------------------------------------------------------------------------------------
class PerformanceTracker(object):
    def __init__(self, serial_number, interface=DEFAULT_INTERFACE):
        self._client = ShenziClient(serial_number, interface=interface)
        self._header = HEADER

        self._timer_thread = Thread()
        self._reporting_thread = Thread()
        self._kill_switch = Event()
        self.is_running = Event()
        self._report_lock = Lock()
        self._initialize_values()

    def set_header(self, new_header):
        self._header = new_header

    def start(self, reporting_interval):
        """
        Initialize variables, print header, and start the reporting loop thread
        """
        if self.is_running.isSet():
            print cfg.StrFmt.Notice("performance tracker is already running")
            return
        self.is_running.set()
        self._kill_switch.clear()
        self._initialize_values(time.time())
        self._timer_thread = Thread(target=self._report, args=(reporting_interval,),
                                        name="Performance Tracker Timer Thread")
        self._timer_thread.start()

    def stop(self):
        """
        Set the kill switch and wait for the reporting loop thread to finish
        """
        self._kill_switch.set()
        if self._timer_thread.isAlive():
            self._timer_thread.join(5)
        if self._reporting_thread.isAlive():
            self._reporting_thread.join(5)
        self._client.close()
        print cfg.StrFmt.Notice("PerformanceTracker. final response count : "+str(self._resp_count))
        self.is_running.clear()

    def log_op(self, latency=None, value=0):
        """
        Used by the owning script to log latency and bytes transfered for a given message
        """
        with self._report_lock:
            self._resp_count += 1
            self._b1 += value
            if latency:
                self._lat_sum += latency
                self._lat_max = max(latency,self._lat_max)
                self._lat_min = min(latency,self._lat_min)
                self._lat_resp_count += 1

    def _initialize_values(self, t0=0):
        # Helpful method for setup
        self._t0 = t0
        self._b0 = self._b1 = 0
        self._resp_count = 0
        self._lat_resp_count = 0
        self._lat_sum = 0
        self._lat_min = ''
        self._lat_max = None
        if not self._client.is_connected:
            self._client.connect(max_attempts=1)

    def _report(self, reporting_interval):
        # Continuous loop that will wait (used instead of sleep so it's interruptible) for
        # the given reporting interval and then spawn a thread to report data
        print ','.join(self._header)
        while not self._kill_switch.isSet():
            self._kill_switch.wait(reporting_interval)
            if self._reporting_thread.isAlive():
                self._reporting_thread.join()
            self._reporting_thread = Thread(target=self._print_data,name="Performance Tracker Report Thread")
            self._reporting_thread.start()

    def _print_data(self):
        # Snapshot the current data and then report according to the header defined up top
        snapshot = self._snapshot_data()
        if not self._kill_switch.isSet():
            output = []
            for field in self._header:
                if field in snapshot:
                    output.append(str(snapshot[field]))
                else:
                    output.append('')
            print ','.join(output)

    def _snapshot_data(self):
        # Snapshot the necessary information, calculate the rest, and return a dictionary of values
        snapshot = {}

        # Wait for data lock to grab current data
        with self._report_lock:
            time_stamp = time.time()
            snapshot['bytes_xfer_total'] = self._b1
            snapshot['resp_count_total'] = self._resp_count
            snapshot['latency_max'] = self._lat_max
            snapshot['latency_min'] = self._lat_min
            lat_resp_count = self._lat_resp_count
            lat_sum = self._lat_sum

            self._lat_resp_count = 0
            self._lat_sum = 0
            self._lat_max = None
            self._lat_min = ''

        if self._kill_switch.isSet():
            return snapshot

        # Get getlog info from the drive
        snapshot.update(self._retrieve_getlog_data())

        # Calculate / format other data
        if lat_resp_count != 0:
            snapshot['latency_ave'] = (lat_sum/lat_resp_count)
        if not snapshot['latency_max']:
            del snapshot['latency_max']
        snapshot['bytes_xfer'] = snapshot['bytes_xfer_total'] - self._b0
        snapshot['MB/s'] = (snapshot['bytes_xfer']/(time_stamp-self._t0))*.000001
        snapshot['time_stamp'] = datetime.datetime.fromtimestamp(time_stamp).strftime('%Y/%m/%d %H:%M:%S')
        snapshot['ipv4_addr'] = self._client.hostname
        snapshot['serial_number'] = self._client.serial_number
        self._t0 = time_stamp
        self._b0 = snapshot['bytes_xfer_total']
        return snapshot

    def _retrieve_getlog_data(self):
        if not self._client.is_connected:
            status = self._client.connect(max_attempts=1)
            if status != 0:
                print cfg.StrFmt.Notice('PerformanceTracker. [Errno '+str(status)+'] failed to connect for getlog')
                return {}

        response = self._client.blocking_cmd('get_log',types=[1,2], timeout=GET_LOG_TIMEOUT)
        if response['success']:
            results = {'percent_full':("%.2f" % float(response['cmd'].body.getLog.capacity.portionFull*100))}
            for temp in response['cmd'].body.getLog.temperatures:
                if temp.name == "HDA":
                    results['hda_temp'] = str(temp.current)
                elif temp.name == "CPU":
                    results['cpu_temp'] = str(temp.current)
            return results
        print cfg.StrFmt.Notice('PerformanceTracker. failed get_log:'+cfg.StrFmt.ProtoStatus(response['cmd'].status))
        return {}

# -------------------------------------------------------------------------------------------------
# Performance Tracker for Multi-client work
# -------------------------------------------------------------------------------------------------
class MultiClientPerformanceTracker(PerformanceTracker):
    def __init__(self, serial_number, num_clients, queue_depth, interface=DEFAULT_INTERFACE, report_max_lat=False):
        self.report_max_lat = report_max_lat
        self._queue_depth = queue_depth
        client_id_header = [str(x) for x in range(num_clients)]
        if self.report_max_lat:
            self._clientID_dict = {x:None for x in client_id_header}
        else:
            self._clientID_dict = {x:0 for x in client_id_header}
        super(MultiClientPerformanceTracker, self).__init__(serial_number, interface)
        self._header = MULTI_CLIENT_HEADER + client_id_header

    def log_op(self, clientID, latency=None,value=0):
        with self._report_lock:
            try:
                if self.report_max_lat:
                    self._clientID_dict[clientID] = max(self._clientID_dict[clientID], latency)
                else:
                    self._clientID_dict[clientID] += value
            except KeyError:
                return
            self._resp_count += 1
            self._b1 += value
            if latency:
                self._lat_sum += latency
                self._lat_max = max(latency, self._lat_max)
                self._lat_min = min(latency, self._lat_min)
                self._lat_resp_count += 1

    def _initialize_values(self, t0=0):
        if self.report_max_lat:
            self._clientID_dict = {x:None for x in self._clientID_dict.keys()}
        else:
            self._clientID_dict = {x:0 for x in self._clientID_dict.keys()}
        super(MultiClientPerformanceTracker, self)._initialize_values(t0)

    def _snapshot_data(self):
        # Snapshot the necessary information, calculate the rest, and return a dictionary of values
        snapshot = {}

        # Wait for data lock to grab current data
        with self._report_lock:
            time_stamp = time.time()
            client_data = self._clientID_dict.copy()
            snapshot['bytes_xfer_total'] = self._b1
            snapshot['latency_max'] = self._lat_max
            snapshot['latency_min'] = self._lat_min
            lat_num_ops = self._lat_resp_count
            lat_sum = self._lat_sum

            if self.report_max_lat:
                self._clientID_dict = {x:None for x in self._clientID_dict.keys()}
            else:
                self._clientID_dict = {x:0 for x in self._clientID_dict.keys()}
            self._lat_resp_count = 0
            self._lat_sum = 0
            self._lat_max = None
            self._lat_min = ''

        if self._kill_switch.isSet():
            return snapshot

        # Get getlog info from the drive
        snapshot.update(self._retrieve_getlog_data())

        # Calculate / format other data
        if lat_num_ops != 0:
            snapshot['latency_ave'] = (lat_sum/lat_num_ops)
        new_bytes = snapshot['bytes_xfer_total'] - self._b0
        if self.report_max_lat:
            for clientID in client_data:
                if client_data[clientID]:
                    snapshot[clientID] = client_data[clientID]
        else:
            if new_bytes > 0:
                for clientID in client_data:
                    snapshot[clientID] = ("%.2f" % ((client_data[clientID] / float(new_bytes)) * 100))
        if not snapshot['latency_max']:
            del snapshot['latency_max']
        snapshot['MB/s'] = (new_bytes/(time_stamp-self._t0))*.000001
        snapshot['time_stamp'] = datetime.datetime.fromtimestamp(time_stamp).strftime('%Y/%m/%d %H:%M:%S')
        snapshot['serial_number'] = self._client.serial_number
        snapshot['queue_depth'] = self._queue_depth
        snapshot['num_connections'] = len(self._clientID_dict)
        self._t0 = time_stamp
        self._b0 = snapshot['bytes_xfer_total']
        return snapshot