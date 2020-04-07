"""
ShenziClient
Usage: N/A
Purpose: A child of kinetic python client, it leverages the local
         DriveStateMonitor (DSM) to work with serial_number instead of
         ip address, and to offer blocking commands.

        **Look at shenzi/README.md for status description**

        - Unique to Shenzi Client
            * verbosity (attr)
                - controls what level of information to print
            * connect (method)
                - Based on a serial number and optionally a specific
                  interface name
                - Works with DSM to get all network information for that
                  serial number
            * status_dsm (method)
                - Communicates a status to the local DSM
            * retrieve_mcast_info (method)
                - Queries multicast data from the local DSM
            * Blocking commands
                The following data structure is returned, each field
                populated with the one of the listedsted possibilities.
                    {'success': [True | False],
                     'msg'    : [None | <msg>],
                     'cmd'    : [None | <cmd>],
                     'value'  : [None | <value>]}
"""
import os
import sys
import time
import json
import socket
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
from General import communicate_with_dsm
if cfg.Tools.CLIENT_PATH:
    import imp
    file, pathname, description = imp.find_module('kv_client', [cfg.Tools.CLIENT_PATH])
    kv_client = imp.load_module('kv_client', file, pathname, description)
from kv_client import Client, kinetic_pb2

CONNECTION_TIMEOUT = 30
CONNECTION_MAX_ATTEMPTS = max
DSM_STATUS_ATTEMPT_MAX = 5

class ShenziClient(Client):
    def __init__(self, serial_number, interface=None, verbosity=0, **kwargs):
        super(ShenziClient, self).__init__(**kwargs)
        self.serial_number = serial_number
        self.interface = interface
        self.verbosity = verbosity

    @property
    def verbosity(self):
        return self._verbosity

    @verbosity.setter
    def verbosity(self, verbosity):
        """
        verbosity is what level of information to print
        0 = Nothing
        1 = Only Errors
        2 = All ShenziClient Outputs
        3 = All ShenziClient Outputs and Client debug turned on
        """
        self._verbosity = verbosity
        if verbosity >= 3:
            self.debug=True
        else:
            self.debug=False

    def _stdout(self, level, msg):
        if level <= self.verbosity:
            print cfg.StrFmt.Notice(msg)

    def _validate_ip_addr(self, ip_list):
        """
        Verify that ips in the given list are real ip addresses

        Returns:
            valid (list)
        """
        valid = []
        for ip in ip_list:
            try:
                socket.inet_aton(ip)
            except socket.error:
                continue
            valid.append(ip)
        return valid

    def connect(self, timeout=CONNECTION_TIMEOUT, max_attempts=CONNECTION_MAX_ATTEMPTS):
        """
        Get connection information from DSM multicast and try to connect
        Once successfully connected verify the serial number
        Secure flag will form an ssl connection
        If both connection attempt parameters are populated, then both are used
        If neither connection attempt parameters are populated, then default timeout is used

        Returns:
            Status : (int) Look at shenzi/README.md for status descriptions
        """
        # Get information from DSM
        mcast_data = self.retrieve_mcast_info()
        # If multicast failed to get all information but you have what you need to connect,
        # don't fail out. Example: I'm missing port info but have a tlsPort and am trying to
        # connect an ssl client.
        if mcast_data['status'] == 211 and len(mcast_data['response']['ip_list']) != 0 \
            and ((self.use_ssl and mcast_data['response']['tlsPort'] != None) \
                or (not self.use_ssl and mcast_data['response']['port'] != None)):
            mcast_data['status'] = 0
        # Fail out if you don't have necessary connection info
        if mcast_data['status'] != 0:
            return mcast_data['status']
        mcast_data = mcast_data['response']

        # Try to connect to each ip in the list
        for ip in mcast_data['ip_list']:
            # Create python client
            if self.use_ssl:
                port = mcast_data['tlsPort']
            else:
                port = mcast_data['port']
            self.hostname = ip
            self.port = port

            # Attempt to connect
            self._stdout(2, "attempting connection \tip: "+str(ip)+" port: "+str(port))
            attempt_count = 0
            t0 = time.time()
            while (time.time()-t0 < timeout) and (attempt_count < max_attempts):
                super(ShenziClient, self).connect()
                if self.is_connected:
                    drive_config = self.sign_on_msg.body.getLog.configuration
                    # Upon connection validate serial number using sign on message
                    if drive_config.serialNumber != self.serial_number:
                        self._stdout(1, "[Errno 201] Serial number mismatch on connection (connected to "+\
                                        str(drive_config.serialNumber)+")")
                        return 201
                    else:
                        self._stdout(2, "successfully connected\tip: "+str(ip)+\
                                                               " port: "+str(port)+\
                                                               "\tkinetic: "+str(drive_config.version))
                        return 0
                attempt_count += 1
            self._stdout(1, "[Errno 200] failed connection\tip: "+str(ip)+" port: "+str(port))
        return 200

    def status_dsm(self, msg):
        """
        Sends status to the local DSM

        Returns:
            Status : (int) Look at shenzi/README.md for status descriptions
        """
        # Compose status message
        status = {'serial_number': self.serial_number,
                  'time_stamp': time.strftime('%Y/%m/%d %H:%M:%S'),
                  'status': str(msg)}

        dsm_response = communicate_with_dsm(ip='127.0.0.1', port=cfg.Network.DSM_PORT_STATUS,
                                            send_data=json.dumps(status), max_attempts=DSM_STATUS_ATTEMPT_MAX)
        if dsm_response['status'] != 0:
            self._stdout(1, "StatusSend."+dsm_response['response'])
        return dsm_response['status']

    def retrieve_mcast_info(self):
        """
        Queries the local DSM for multicast information and then returns a filtered response

        Returns:
            {'status'   : (int) Look at shenzi/README.md for status descriptions,
             'response' : {'ip_list' : (list),
                           'tlsPort' : [None | (int)],
                           'port'    : [None | (int)]}}
        """
        output = {'status' : 20,
                  'response' : {'ip_list':[],
                                'port':None,
                                'tlsPort':None}}

        # Query DSM
        dsm_response = communicate_with_dsm(ip='127.0.0.1', port=cfg.Network.DSM_PORT_QUERY,
                                            send_data='m', drives_of_interest=[self.serial_number])
        if dsm_response['status'] != 0:
            self._stdout(1, "McastQuery."+dsm_response['response'])
            output['status'] = dsm_response['status']
            return output

        if type(dsm_response['response']) != dict:
            self._stdout(1, "DSM Mcast Data Error [Errno 210]: "+str(dsm_response['response']))
            output['status'] = 210
            return output

        # Look for serial number in mcast data
        dsm_response = dsm_response['response']
        if self.serial_number not in dsm_response:
            self._stdout(1, "[Errno 211] Could not find serial number in multicast data")
            output['status'] = 211
            return output

        # Look for port information in that serial number's mcast data
        dsm_response = dsm_response[self.serial_number]
        if 'port' not in dsm_response:
            self._stdout(1, "[Errno 211] No port listed for this serial number")
            output['status'] = 211
            return output
        output['response']['port'] = dsm_response['port']
        if 'tlsPort' not in dsm_response:
            self._stdout(1, "[Errno 211] No tls port listed for this serial number")
            output['status'] = 211
            return output
        output['response']['tlsPort'] = dsm_response['tlsPort']

        # Look for network interface information in that serial number's mcast data
        if 'network_interfaces' not in dsm_response:
            self._stdout(1, "[Errno 211] No network interface data listed for this serial number")
            output['status'] = 211
            return output

        # Grab all available ipv4 if no interface is specified
        if self.interface == None:
            ip_list = []
            for interface in dsm_response['network_interfaces']:
                if 'ipv4_addr' in interface:
                    ip_list.append(interface['ipv4_addr'])
            output['response']['ip_list'] = self._validate_ip_addr(ip_list)
            output['status'] = 0
            return output

        # Grab the ipv4 for the specified interface
        else:
            for interface in dsm_response['network_interfaces']:
                if 'name' in interface:
                    if self.interface == interface['name']:
                        if 'ipv4_addr' in interface:
                            output['response']['ip_list'] = self._validate_ip_addr([interface['ipv4_addr']])
                            output['status'] = 0
                            return output
                        else:
                            self._stdout(1, "[Errno 211] Could not find ipv4 for interface "+\
                                            str(self.interface)+" in multicast data")
                            output['status'] = 211
                            return output
            self._stdout(1, "[Errno 211] Could not find Interface "+str(self.interface)+\
                            " in Multicast Data")
            output['status'] = 211
            return output

    # Blocking Client Cmd -------------------------------------------------------------------------
    def blocking_cmd(self, command, **kwargs):
        """
        Calls client.command(**kwargs) with the option of blocking
        - Blocking commands will issue the command, wait for a response, and then return (success
          means a successful callback)

        Returns:
            {'success': [True | False],
             'msg'    : [None | <msg>],
             'cmd'    : [None | <cmd>],
             'value'  : [None | <value>]}
        """
        output = {'success': False,
                  'msg'    : None,
                  'cmd'    : None,
                  'value'  : None}

        # Save current delegate settings
        previous_delegate = self.callback_delegate

        # Issue command and wait for response
        self.callback_delegate = self._blocking_callback(output)
        try:
            if kwargs:
                getattr(self, command) (**kwargs)
            else:
                getattr(self, command) ()
        except AttributeError:
            self._stdout(1, "No Client Method '"+str(command)+"'")
            output['status'] = "No Client Method '"+str(command)+"'"
            return output
        self.wait_q(outstanding=0)

        # Restore original delegate settings and return the command response
        self.callback_delegate = previous_delegate
        return output

    def _blocking_callback(self, output):
        def wrapper(msg, cmd, value):
            output['success'] = bool(cmd.status.code == kinetic_pb2.Command.Status.SUCCESS)
            output['msg'] = msg
            output['cmd'] = cmd
            output['value'] = value
        return wrapper
