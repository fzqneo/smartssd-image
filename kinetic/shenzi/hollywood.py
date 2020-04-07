#!/usr/bin/env python
"""
usage: hollywood.py [-info | -set_fan_speed SET_FAN_SPEED | -power {ON,OFF}] [--location LOCATION]
        -info : get information about the chassis
        -set_fan_speed SET_FAN_SPEED : set the fan speed on the chassis. Must be in this range [20, 100]
        -power {ON,OFF} : issue a power command to a set of drives, a slot, or an entire chassis
        -location LOCATION : an option to issue a power command on a specific slot in a specific bmc. format [ip]:[slot]
"""
import time
from argparse import ArgumentParser
import Mine.Config as cfg
from Support.CSVTable import CSVTable
from Support.General import get_drive_list_input, communicate_with_dsm, communicate_with_bmc

class HollywoodException(Exception):
    def __init__(self, value):
        self.value = cfg.StrFmt.Notice("Hollywood", value)

    def __str__(self):
        return repr(self.value)

def format_error(*args):
    return cfg.StrFmt.Notice("Hollywood", *args)

def get_location(drives_of_interest):
    if len(cfg.Network.DSM_IPs) == 0:
        raise HollywoodException("no dsm ips listed in Mine.Config")
    if drives_of_interest is None:
        raise HollywoodException("get_location cannot operate on drives_of_interest = None")

    # Get world wide names from the DSM
    missing_mcast = {d:None for d in drives_of_interest}
    drives = {}
    for dsm_ip in cfg.Network.DSM_IPs:
        dsm_results = communicate_with_dsm(ip=dsm_ip, port=cfg.Network.DSM_PORT_QUERY, send_data='m', drives_of_interest=drives_of_interest)
        if dsm_results['status'] != 0:
            print format_error('failed dsm query', str(results['results']))
            continue
        else:
            dsm_results = dsm_results['response']
            for serial_number in dsm_results:
                drives[dsm_results[serial_number]['world_wide_name'].replace(' ','')] = {}
                drives[dsm_results[serial_number]['world_wide_name'].replace(' ','')]['serial_number'] = serial_number
                del missing_mcast[serial_number]

    # Get slots from the bmc
    missing_bmc = {d:None for d in drives_of_interest if d not in missing_mcast}
    for bmc_ip in cfg.Network.BMC_IPs:
        results = communicate_with_bmc(bmc_ip, False, "slots")
        if not results['success']:
            print format_error('failed bmc query', str(results['results']))
            continue
        results = results['results']
        for slot in results['slots']:
            if slot['worldwidename'] in drives:
                drives[slot['worldwidename']]['location'] = bmc_ip+":"+str(slot['location'])
                del missing_bmc[drives[slot['worldwidename']]['serial_number']]

    # Delete any entries that don't have a location
    for world_wide_name in drives:
        if 'location' not in drives[world_wide_name]:
            del drives[world_wide_name]

    return drives, missing_mcast.keys(), missing_bmc.keys()

def main():
    parser = ArgumentParser()
    mutually_ex_group = parser.add_mutually_exclusive_group(required=True)
    mutually_ex_group.add_argument("-info", action="store_true", help="get information about the chassis")
    mutually_ex_group.add_argument("-set_fan_speed", type=int, help="set the fan speed on the chassis. Must be in this range [20, 100]")
    mutually_ex_group.add_argument("-power",  type=str.upper, choices=['ON', 'OFF'], help="issue a power command to a set of drives, a slot, or an entire chassis")
    parser.add_argument('--location', type=str, help="an option to issue a power command on a specific slot in a specific bmc. format [ip]:[slot]")
    args = parser.parse_args()
    if args.location and not args.power:
        parser.error('location is only useful for the power command')

    if len(cfg.Network.BMC_IPs) < 1:
        raise HollywoodException('no bmc ips listed in Mine.Config.py')

    if args.info:
        for bmc_ip in cfg.Network.BMC_IPs:
            print bmc_ip
            temp = communicate_with_bmc(bmc_ip, False, "chassis")
            if not temp['success']:
                print format_error('failed bmc query for chassis info', str(temp['results']))
            else:
                temp = temp['results']['info']
                for item in sorted(temp):
                    print "\t"+str(item)+": "+str(temp[item])

            temp = communicate_with_bmc(bmc_ip, False, "environment")
            if not temp['success']:
                print format_error('failed bmc query for environment info', str(temp['results']))
            else:
                temp = temp['results']
                print "\tfanspeeds: "
                fs = {x['location']:x['speed'] for x in temp['fanspeed']}
                for item in sorted(fs):
                    print "\t\t"+str(item)+": "+str(fs[item])

    if args.set_fan_speed:
        if args.set_fan_speed < 20 or args.set_fan_speed > 100:
            parser.error("fan speed must be between 20 and 100 (inclusive)")
        for bmc_ip in cfg.Network.BMC_IPs:
            user_decision = raw_input("set fan speed on chassis "+bmc_ip+" to "+str(args.set_fan_speed)+"? [y/n]\n")
            if user_decision[0].lower() == 'y':
                temp = communicate_with_bmc(bmc_ip, True, "environment", None, {'speed':args.set_fan_speed})
                if not temp['success']:
                    print format_error(str(temp['results']))

    if args.power:
        if args.location:
            ip, slot = args.location.split(':')
            print "power:"+str(args.power)+" | bmc:"+str(ip)+" | slot:"+str(slot)
            temp = communicate_with_bmc(ip, True, "slots", int(slot), {'power':str(args.power)})
            if not temp['success']:
                print format_error('failed command', str(temp['results']))
        else:
            # Look for drives to operate on
            output_drives, _ = get_drive_list_input()

            # If there are drives, find the slots
            if output_drives:
                location_mapping, missing_mcast, missing_bmc = get_location(output_drives)
                if len(missing_mcast) > 0:
                    print format_error("failed to find multicast information for: "+",".join(missing_mcast))
                if len(missing_bmc) > 0:
                    print format_error("failed to find bmc information for: "+",".join(missing_bmc))
                if len(location_mapping) == 0:
                    print format_error('could not find any location information for the drives given')
                    return

                for drive in location_mapping:
                    ip, slot = location_mapping[drive]['location'].split(':')
                    print "power:"+str(args.power)+"|bmc:"+str(ip)+"|slot:"+str(slot)+"|drive:"+str( location_mapping[drive]['serial_number'])
                    temp = communicate_with_bmc(ip, True, "slots", int(slot), {'power':str(args.power)})
                    if not temp['success']:
                        print format_error('failed command', str(temp['results']))
            else:
                for bmc_ip in cfg.Network.BMC_IPs:
                    user_decision = raw_input("Are you sure you want to issue power:"+args.power+" to all slots in chassis:"+bmc_ip+"? [y/n]\n")
                    if user_decision[0].lower() == 'y':
                        temp = communicate_with_bmc(bmc_ip, True, "slots", None, {'power':str(args.power)})
                        if not temp['success']:
                            print format_error(str(temp['results']))

if __name__ == "__main__":
    main()
