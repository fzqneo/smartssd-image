#!/usr/bin/python
"""
Get Drive List
Usage: [drives] | ./get_drive_list.py [[c ? g ? l ? m ? s] | S 'x' | C] --all
        drives : an optional list of drives to show status for
        all : Display information for all drives the DSM has data on.
              If a drive list is pipped in, this flag is ignored.
              If there's a failure to read mine.csv and nothing is pipped in, this flag is automatically set
        c : Chassis data
        g : Getlog data, this will output get_log(messages) to a file in the Results directory
        l : Slot location
        m : Multicast data
        s : Most recent script status
        S : The 'x' most recent status updates, default show all
        C : Raw bmc data (not mapped to serial_numbers in multicast)
"""
import os
import sys
import time
from argparse import ArgumentParser
import Mine.Config as cfg
from Support.CSVTable import CSVTable
from Support.ShenziClient import ShenziClient
from Support.General import get_drive_list_input, communicate_with_dsm, communicate_with_bmc

SHENZI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi")
RESULTS_DIR = os.path.join(SHENZI_PATH,"Mine","Results")
MINE_DRIVE_LIST = os.path.join(SHENZI_PATH,"Mine","DriveLists","mine.csv")

class GetDriveListException(Exception):
    def __init__(self, value):
        self.value = "GetDriveList."+time.strftime('%Y/%m/%d_%H:%M:%S')+"|"+str(value).replace("\n",";")

    def __str__(self):
        return repr(self.value)

# -------------------------------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------------------------------
def query_dsm(query, drives_of_interest=None):
    if len(cfg.Network.DSM_IPs) == 0:
        raise GetDriveListException("no dsm ips listed in "+str(MINE_DRIVE_LIST))
    dsm_dict = {}
    for dsm_ip in cfg.Network.DSM_IPs:
        results = communicate_with_dsm(ip=dsm_ip, port=cfg.Network.DSM_PORT_QUERY,
                                       send_data=query, drives_of_interest=drives_of_interest)
        if results['status'] != 0:
            raise GetDriveListException("failed dsm query|"+str(results['response']))
        else:
            if query == 'm':
                for drive in results['response']:
                    results['response'][drive]['dsm_ip'] = dsm_ip
            dsm_dict.update(results['response'])
    if query == 'm':
        for serial_number in dsm_dict:
            dsm_dict[serial_number]['serial_number'] = serial_number
            # Flatten network interfaces data
            if 'network_interfaces' in dsm_dict[serial_number]:
                dsm_dict[serial_number].update(prep_interface_data(dsm_dict[serial_number]['network_interfaces']))
                del dsm_dict[serial_number]['network_interfaces']
            if 'world_wide_name' in dsm_dict[serial_number]:
                dsm_dict[serial_number]['world_wide_name'] = "".join(dsm_dict[serial_number]['world_wide_name'].split()).lower()
            if 'last_seen' in dsm_dict[serial_number]:
                dsm_dict[serial_number]['last_seen_mcast'] = dsm_dict[serial_number]['last_seen']
                del dsm_dict[serial_number]['last_seen']
    return dsm_dict

def query_bmc(key):
    if len(cfg.Network.BMC_IPs) == 0:
        raise GetDriveListException("no bmc ips listed in "+str(MINE_DRIVE_LIST))
    slot_data = {}
    for bmc_ip in cfg.Network.BMC_IPs:
        results = communicate_with_bmc(ip=bmc_ip, is_put=False, service="slots")
        if results['success']:
            for slot in results['results']['slots']:
                slot['location'] = bmc_ip+":"+str(slot['location'])
                slot_data[slot[key]] = dict(slot)
        else:
            raise GetDriveListException("failed bmc query|"+str(results['results']))
    for info in slot_data:
        if 'network_interfaces' in slot_data[info]:
            slot_data[info].update(prep_interface_data(slot_data[info]['network_interfaces']))
            del slot_data[info]['network_interfaces']
        if 'last_seen' in slot_data[info]:
            slot_data[info]['last_seen_bmc'] = slot_data[info]['last_seen']
            del slot_data[info]['last_seen']
    return slot_data

def query_getlog(drives_of_interest):
    get_log_data = {}
    for drive in drives_of_interest:
        client = ShenziClient(drive)
        if client.connect(max_attempts=1) != 0:
            continue
        get_log_data[drive] = {}

        # configuration
        get_log_data[drive]['serial_number'] = client.sign_on_msg.body.getLog.configuration.serialNumber
        get_log_data[drive]['firmware_version'] = client.sign_on_msg.body.getLog.configuration.version
        get_log_data[drive]['model'] = client.sign_on_msg.body.getLog.configuration.model
        get_log_data[drive]['compilation_date'] = client.sign_on_msg.body.getLog.configuration.compilationDate
        get_log_data[drive]['source_hash'] = client.sign_on_msg.body.getLog.configuration.sourceHash
        get_log_data[drive]['protocol_version'] = client.sign_on_msg.body.getLog.configuration.protocolVersion
        get_log_data[drive]['protocol_compilation_date'] = client.sign_on_msg.body.getLog.configuration.protocolCompilationDate
        get_log_data[drive]['protocol_source_hash'] = client.sign_on_msg.body.getLog.configuration.protocolSourceHash
        get_log_data[drive]['current_power_level'] = client.sign_on_msg.body.getLog.configuration.currentPowerLevel

        # limits
        get_log_data[drive]['max_key_size'] = client.sign_on_msg.body.getLog.limits.maxKeySize
        get_log_data[drive]['max_value_size'] = client.sign_on_msg.body.getLog.limits.maxValueSize
        get_log_data[drive]['max_version_size'] = client.sign_on_msg.body.getLog.limits.maxVersionSize
        get_log_data[drive]['max_tag_size'] = client.sign_on_msg.body.getLog.limits.maxTagSize
        get_log_data[drive]['max_connections'] = client.sign_on_msg.body.getLog.limits.maxConnections
        get_log_data[drive]['max_outstanding_read_requests'] = client.sign_on_msg.body.getLog.limits.maxOutstandingReadRequests
        get_log_data[drive]['max_outstanding_write_requests'] = client.sign_on_msg.body.getLog.limits.maxOutstandingWriteRequests
        get_log_data[drive]['max_message_size'] = client.sign_on_msg.body.getLog.limits.maxMessageSize
        get_log_data[drive]['max_key_range_count'] = client.sign_on_msg.body.getLog.limits.maxKeyRangeCount
        get_log_data[drive]['max_identity_count'] = client.sign_on_msg.body.getLog.limits.maxIdentityCount
        get_log_data[drive]['max_pin_size'] = client.sign_on_msg.body.getLog.limits.maxPinSize

        get_log = client.blocking_cmd("get_log", types=[1,2,5,7], device='firmware_version')
        if get_log['success']:
            # messages
            get_log_data[drive]['messages'] = get_log['cmd'].body.getLog.messages

            # temperatures
            for item in get_log['cmd'].body.getLog.temperatures:
                if item.name == "HDA":
                    get_log_data[drive]['hda_temp'] = str(item.current)
                elif item.name == "CPU":
                    get_log_data[drive]['cpu_temp'] = str(item.current)

            # capacities
            get_log_data[drive]['nominal_capacity_in_bytes'] = get_log['cmd'].body.getLog.capacity.nominalCapacityInBytes
            get_log_data[drive]['portion_full'] = get_log['cmd'].body.getLog.capacity.portionFull

            # f3 version
            get_log_data[drive]['f3_version'] = get_log['value']

        get_log = client.blocking_cmd("get_log", types=[7], device='uboot_version')
        if get_log['success']:
            # uboot version
            get_log_data[drive]['uboot_version'] = get_log['value']
    return get_log_data

def prep_interface_data(interface_data):
    count = 0
    prepped_interface_data = {}
    for interface in interface_data:
        label = 'network_interfaces.'+str(count)
        for info in interface:
            temp_label = label+'.'+str(info)
            prepped_interface_data[temp_label] = interface[info]
        count += 1
    return prepped_interface_data

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Input arguments
    parser = ArgumentParser(usage='[drives] | ./get_drive_list [[c ? g ? l ? m ? s] | S \'x\' | C] --all')
    parser.add_argument("--all", help="Display information for all drives the DSM has data on."+\
                                        " If a drive list is pipped in, this flag is ignored."+\
                                        " If there's a failure to read mine.csv and nothing is"+\
                                        " pipped in, this flag is automatically set", action="store_true")
    parser.add_argument("-c", help="Chassis information", action="store_true")
    parser.add_argument("-g", help="Getlog information, this will output get_log(messages) to a file in the Results directory", action="store_true")
    parser.add_argument("-l", help="Slot location", action="store_true")
    parser.add_argument("-m", help="Multicast information", action="store_true")
    parser.add_argument("-s", help="Most recent status history with time stamps", action="store_true")
    mutually_ex_group = parser.add_mutually_exclusive_group()
    mutually_ex_group.add_argument("-S", help="The 'x' most recent status updates, default show all",
                              nargs='?', const=50, type=int, default=False)
    mutually_ex_group.add_argument("-C", help="Raw bmc data (not mapped to serial_numbers in multicast)", action="store_true")

    args = parser.parse_args()
    large_args = [args.C, args.S]
    small_args = [args.c, args.g, args.l, args.m, args.s]
    if (large_args.count(False) != len(large_args)) and (True in small_args):
        parser.error('Cannot combine S or C with any other argument, type -h for help')

    # Gather any drive input to filter by
    output_drives, _ = get_drive_list_input()

    # If there weren't any pipped in drives, check for mine.csv
    if output_drives is None and not args.all:
        output_drives, _ = get_drive_list_input(file_name=MINE_DRIVE_LIST)
        # If there were no drives piped in and there is no mine.csv, report all
        if output_drives is None:
            args.all = True
        # If mines.csv exists but has no drives, error out
        elif len(output_drives) == 0:
            raise GetDriveListException(str(MINE_DRIVE_LIST)+" is empty")

    # Show all chassis data
    if args.C:
        bmc_data = query_bmc(key='location')
        reporting_data = CSVTable('location')
        for info in bmc_data:
            reporting_data.insert_data(bmc_data[info])
        reporting_data.print_table()

    # Show the 'x' most recent status updates, default show all
    elif args.S != False:
        status_data = query_dsm('s', output_drives)
        output = []
        for serial_number in status_data:
            temp = []
            count = min(args.S, len(status_data[serial_number]))

            for i in range(1, count+1):
                temp.append({'status_time_stamp':status_data[serial_number][-i]['time_stamp'],
                                'status':status_data[serial_number][-i]['status'],
                                'serial_number':serial_number})
            output += list(reversed(temp))
        print "serial_number,status_time_stamp,status"
        for item in output:
            print item['serial_number']+","+item['status_time_stamp']+","+item['status']

    # Combination data reporting
    else:
        reporting_data = CSVTable()
        header = []

        # Default data reporting
        if not (True in small_args):
            header = ['serial_number','last_seen_mcast','firmware_version',
                      '*ipv4_addr','status_time_stamp','status']
            mcast_data = query_dsm('m', output_drives)
            status_data = query_dsm('s', output_drives)
            for serial_number in mcast_data:
                reporting_data.insert_data(mcast_data[serial_number])
            for serial_number in status_data:
                temp = {'status_time_stamp':status_data[serial_number][-1]['time_stamp'],
                        'status':status_data[serial_number][-1]['status'],
                        'serial_number':serial_number}
                reporting_data.insert_data(temp)

        # Combination flags
        else:
            bmc_data = {}
            mcast_data = {}
            status_data = {}
            get_log_data = {}

            if args.all:
                mcast_data = query_dsm('m')
                output_drives = mcast_data.keys()

            # Complete multicast data
            if args.m:
                if not mcast_data:
                    mcast_data = query_dsm('m', output_drives)
                for serial_number in mcast_data:
                    reporting_data.insert_data(mcast_data[serial_number])

            # Most recent status
            if args.s:
                status_data = query_dsm('s', output_drives)
                for serial_number in status_data:
                    temp = {'status_time_stamp':status_data[serial_number][-1]['time_stamp'],
                            'status':status_data[serial_number][-1]['status'],
                            'serial_number':serial_number}
                    reporting_data.insert_data(temp)

            # Complete chassis data
            if args.c:
                bmc_data = query_bmc(key='worldwidename')
                if bmc_data:
                    if not mcast_data:
                        mcast_data = query_dsm('m', output_drives)
                    for serial_number in mcast_data:
                        if mcast_data[serial_number]['world_wide_name'] in bmc_data:
                            temp = bmc_data[mcast_data[serial_number]['world_wide_name']]
                            temp['serial_number'] = serial_number
                            reporting_data.insert_data(temp)

            # Slot location
            if args.l:
                if not bmc_data:
                    bmc_data = query_bmc(key='worldwidename')
                if bmc_data:
                    if not mcast_data:
                        mcast_data = query_dsm('m', output_drives)
                    for serial_number in mcast_data:
                        if mcast_data[serial_number]['world_wide_name'] in bmc_data:
                            temp = {'serial_number':serial_number,
                                    'location':bmc_data[mcast_data[serial_number]['world_wide_name']]['location']}
                            reporting_data.insert_data(temp)

            # Get Log data
            if args.g:
                get_log_data = query_getlog(output_drives)
                for serial_number in get_log_data:
                    # Write out messages to a Results file
                    if 'messages' in get_log_data[serial_number]:
                        file_name = os.path.join(RESULTS_DIR,(time.strftime('%Y-%m-%d_%H-%M-%S')+"_"+serial_number+"_GetLogMessages.csv"))
                        with open(file_name, 'w') as file_handle:
                            file_handle.write(get_log_data[serial_number]['messages'])
                        del get_log_data[serial_number]['messages']

                    # Add the rest of get_log data to drive data
                    reporting_data.insert_data(get_log_data[serial_number])

        reporting_data.print_table(header)

    # Handle stdin to avoid errors when piping data in and out to/from this script
    try:
        sys.stdout.close()
    except:
        pass
    try:
        sys.stderr.close()
    except:
        pass