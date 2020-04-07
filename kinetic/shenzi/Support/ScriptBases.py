"""
Script Bases
Usage: N/A
Purpose: Base classes meant to be inherited by command scripts. Offers the simple start, wait, stop
         API. To use this just inherit the class you want and override the activity method with whatever
         workload you need.
"""
import os
import sys
import time
import json
import socket
from threading import Thread, Event
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
import Support.KeyGenerator as KeyGen
from Support.ShenziClient import ShenziClient
from Support.PerformanceTracker import PerformanceTracker

# -------------------------------------------------------------------------------------------------
# Start Wait Stop API
# -------------------------------------------------------------------------------------------------
class StartWaitStopAPI(object):
    def __init__(self, script_name=''):
        self._kill_switch = Event()
        self._stop_called = Event()
        self._stop_complete = Event()
        self.script_name = str(script_name)
        self._activity_thread = Thread(target=self._activity,
                                        name=self.script_name+' Activity Thread')

    def start(self):
        """
        Clear all events and start the main activity thread
        """
        self._kill_switch.clear()
        self._stop_called.clear()
        self._stop_complete.clear()
        self._activity_thread = Thread(target=self._activity,
                                        name=self.script_name+' Activity Thread')
        self._activity_thread.start()

    def stop(self, activity_call=False, last_call=True):
        """
        Set the appropriate events, wait for main activity thread to finish
        """
        self._stop_called.set()
        self._kill_switch.set()
        if self._activity_thread.isAlive() and not activity_call:
            self._activity_thread.join(30)
        if last_call:
            self._stop_complete.set()

    def wait(self, timeout=31556926, terminate=False):
        """
        Wait for the script to end with some timeout, the default is one year so
        that a wait can be interrupted. If terminate is true then it will call stop on the
        script after a timeout.
        Return value is True if the script finished on it's own and False if the wait timed out.
        """
        script_finished = self._stop_complete.wait(timeout)
        if terminate and not script_finished:
            self.stop()
        return script_finished

    def _activity(self):
        # Override this method with your workload
        pass


# -------------------------------------------------------------------------------------------------
# Start Wait Stop API with Client Management and statusing
# -------------------------------------------------------------------------------------------------
class StartWaitStopClientAPI(StartWaitStopAPI):
    def __init__(self, serial_number, interface, script_name):
        super(StartWaitStopClientAPI, self).__init__(script_name)
        self.status = 1
        self._client = ShenziClient(serial_number, interface, verbosity=2)

    def start(self, verbose=True):
        """
        Clear all events and start the main activity thread
        """
        self.status = 2
        if verbose:
            print cfg.StrFmt.Notice('starting '+self.script_name)
            self._client.status_dsm('starting '+self.script_name)
        super(StartWaitStopClientAPI, self).start()

    def stop(self, activity_call=False, last_call=True, verbose=True):
        """
        Set the appropriate events, wait for main activity thread to finish, and close client
        """
        super(StartWaitStopClientAPI, self).stop(activity_call=activity_call, last_call=False)
        if verbose:
            print cfg.StrFmt.Notice('stopping '+self.script_name)
        if self._client.is_connected:
            if verbose:
                print cfg.StrFmt.Notice('closing client (flush, wait, close)')
            self._client.flush_all_data()
            self._client.wait_q(outstanding=0)
            self._client.close()
        if self.status < 100:
            self.status = 0
        if verbose:
            if activity_call:
                print cfg.StrFmt.Notice('internally stopped '+self.script_name)
                self._client.status_dsm('internally stopped '+self.script_name)
            else:
                print cfg.StrFmt.Notice('stopped '+self.script_name)
                self._client.status_dsm('stopped '+self.script_name)
        if last_call:
            self._stop_complete.set()

# -------------------------------------------------------------------------------------------------
# Start Wait Stop API with Client Management, statusing, a PerformanceTracker, and a KeyGenerator
# -------------------------------------------------------------------------------------------------
class StartWaitStopPerfAPI(StartWaitStopClientAPI):
    """
    Same as Script Base but incorporates a performance tracker and key gen
    It is up to the child class to start it's performance tracker when it sees fit
    """
    def __init__(self, serial_number, interface, reporting_interval, keygen_config, max_num_ops, script_name, verbose=True):
        super(StartWaitStopPerfAPI, self).__init__(serial_number, interface, script_name)
        self._reporting_interval = reporting_interval
        self._performanceTracker = PerformanceTracker(serial_number, interface)
        self._max_num_ops = max_num_ops

        # Try to create a Key Gen
        try:
            key_type, key_specs = KeyGen.parse_config_file(keygen_config)
            self.key_gen = KeyGen.create_keygen(key_type)(key_specs)
        except KeyGen.KeyGeneratorException as e:
            self.status = 311
            if verbose:
                print cfg.StrFmt.Notice('[Errno 311] '+str(e))
                self._client.status_dsm('[Errno 311] failed to create key gen')
            self.stop(verbose=verbose)

    def start(self, verbose=True):
        # Check if you have a key gen
        if self.status >= 100:
            if verbose:
                print cfg.StrFmt.Notice('cannot start with a status of '+str(self.status))
            self.stop()
        else:
            super(StartWaitStopPerfAPI, self).start(verbose=verbose)

    def stop(self, activity_call=False, last_call=True, verbose=True):
        self._performanceTracker.stop()
        super(StartWaitStopPerfAPI, self).stop(activity_call=activity_call, last_call=last_call, verbose=verbose)

    def _validate_limits(self, **kwargs):
        """
        Tells you if the values passed in exceed the maximums reported by the drive limits
        Must have already called connect on client to use

        Returns:
            {'success'  : [True | False],
             'response' : [(str) Error Response | None]}
        """
        # Connect a temporary client
        temp_client = ShenziClient(self._client.serial_number, self._client.interface)
        result = temp_client.connect()
        if result != 0:
            return {'success':False,'response':'failed to connect client. status: '+str(result)}
        temp_client.close()

        limits = temp_client.sign_on_msg.body.getLog.limits
        for key, value in kwargs.iteritems():
            try:
                if value != None and value > getattr(limits, key):
                    return {'success':False,'response':"exceeded drive's reported limit for "+str(key)+\
                                                        ". drive limit="+str(getattr(limits, key))}
            except AttributeError:
                return {'success':False,'response':" failed to find a limit called "+str(key)}
        return {'success':True,'response':None}