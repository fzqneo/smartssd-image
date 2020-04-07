#!/usr/bin/python
"""
Wipe DSM
Usage: ./wipeDSM.py
Purpose: A shortcut script to wipe all mcast data and status histories from the local DSM
"""
import os
import sys
import time
from argparse import ArgumentParser
sys.path.insert(0,os.path.join(os.path.dirname(os.path.realpath(__file__)).split('shenzi')[0],"shenzi"))
import Mine.Config as cfg
from Support.General import communicate_with_dsm

if __name__=="__main__":
    parser = ArgumentParser()
    args = parser.parse_args()
    results = communicate_with_dsm(ip='127.0.0.1', port=cfg.Network.DSM_PORT_QUERY, send_data="w")
    if results['status'] != 0:
        print cfg.StrFmt.Notice("wipeDSM",str(results['response']))
        sys.exit(1)
    else:
        print cfg.StrFmt.Notice("wipeDSM","Success")