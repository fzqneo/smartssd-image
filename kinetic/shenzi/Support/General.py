"""
General Support
Usage: N/A
Purpose: A place to put commonly used functions
"""
import os
import sys
import json
import time
import socket
try:
    import requests
except ImportError:
    pass

SOCKET_BUFFER = 64*2**10
SOCKET_TIMEOUT = 5

BMC_QUERY_TIMEOUT = 60

def communicate_with_dsm(ip, port, send_data, max_attempts=1, drives_of_interest=None):
    """
    Creates a socket to a DSM (local by default), on the specified port. Will send over data and listen for
    response.

    Returns:
        {'status'   : (int) Look at shenzi/README.md for status descriptions,
         'response' : [(json.loads interpretation of data) | (str) | None]}
    """
    output = {'status' : 20,
              'response' : None}

    for i in range(max_attempts):
        # Create Socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((ip, port))
        except socket.error as serr:
            output['response'] = "DSM_Communication. [Errno 010] Socket Error on Creation/Connection: "+str(serr)
            output['status'] = 10
            continue

        # Send Status
        try:
            sock.sendall(send_data)
        except socket.error as serr:
            output['response'] = "DSM_Communication. [Errno 011] Socket Error on Send: "+str(serr)
            output['status'] = 11
            continue

        # Receive Response
        try:
            recieve_data = " "
            t0 = time.time()
            while time.time()-t0 < SOCKET_TIMEOUT and recieve_data[-1] != "\x04":
                recieve_data += sock.recv(SOCKET_BUFFER)
            sock.close()
        except socket.error as serr:
            output['response'] = "DSM_Communication. [Errno 012] Socket Error on Receive: "+str(serr)
            output['status'] = 12
            continue

        # Validate Handshake
        if recieve_data[-1] != "\x04":
            output['response'] = "DSM_Communication. [Errno 013] Handshake Failed"
            output['status'] = 13
            continue

        # Check for DSM Reported Errors
        if 'DSM Query Error' in recieve_data:
            output['response'] = "DSM_Communication. [Errno 014] "+recieve_data[1:-1]
            output['status'] = 14
            continue

        # Return json format / string response from DSM
        output['status'] = 0
        try:
            dsm_data = json.loads(recieve_data[1:-1])
            if drives_of_interest is None:
                output['response'] = dsm_data
            else:
                output['response'] = {drive: dsm_data[drive] for drive in drives_of_interest if drive in dsm_data}
        except ValueError:
            output['response'] = recieve_data[1:-1]
        finally:
            break
    # Return None for failed communications
    return output

def communicate_with_bmc(ip, is_put, service, slot=None, payload=None):
    results = {'success':False,'results':None}
    try:
        if 'requests' not in sys.modules:
            results['results'] = 'failed to import requests module, please install it'
            return
        if slot is None:
            url = "http://%s/api.php/%s" % (ip, service)
        else:
            url = "http://%s/api.php/%s/%d" % (ip, service, slot)
        if is_put:
            if payload is None:
                resp = requests.put(url, timeout=BMC_QUERY_TIMEOUT)
            else:
                resp = requests.put(url, payload, timeout=BMC_QUERY_TIMEOUT)
            resp = resp.content
        else:
            resp = requests.get(url, timeout=BMC_QUERY_TIMEOUT)
            resp = resp.text
        temp = json.loads(resp)
        results['success'] = temp['success']
        results['results'] = temp['results']
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        results['success'] = False
        results['results'] = 'exception in communicate_with_bmc:'+str(e)
    finally:
        return results

def row_to_dict(input_header, row):
    """
    Takes a header (list) and a row (comma delimited string) and returns a dictionary where the
    keys are the header and values are an indexed matching of the row
    """
    row = [x.strip() for x in row.split(",")]
    output = {}
    for index,item in enumerate(row):
        try:
            output[input_header[index]] = item
        except IndexError:
            pass
    return output

def is_serial_num(candidate):
    """
    Takes a string and checks if it would make a valid drive serial number
    """
    if candidate.isalnum() and len(candidate) == 8:
        return True
    else:
        return False

def get_drive_list_input(file_name=None):
    """
    Checks for drives being pipped in, or in a file (if a file_name was given), and
    will return a list of valid serial numbers and a count of invalid serial numbers
    Acceptable input formats: a comma delimited string or a csv
    """
    input_handle = None

    # Check if a file_name was given:
    if file_name is not None:
        try:
            input_handle = open(file_name, 'r')
        except IOError:
            pass
    # Else, check if you detected input being piped in
    elif not sys.stdin.isatty():
        input_handle = sys.stdin

    # If nothing was pipped in and a file couldn't be opened return
    if input_handle == None:
        return None, None
    # Else, proccess drives
    else:
        drives = []
        invalid_count = 0
        line = [x.strip() for x in input_handle.readline().split(",")]

        # Grab csv
        if 'serial_number' in line:
            sn_index = line.index('serial_number')
            while True:
                line = input_handle.readline()
                if not line.strip():
                    break
                line = [x.strip() for x in line.split(",")]
                if not is_serial_num(line[sn_index]):
                    invalid_count += 1
                else:
                    drives.append(line[sn_index])

        # Grab list
        else:
            while True:
                for drive in line:
                    if not is_serial_num(drive):
                        invalid_count += 1
                    else:
                        drives.append(drive)
                line = input_handle.readline()
                if not line.strip():
                    break
                line = [x.strip() for x in line.split(",")]
        return drives, invalid_count
