from __future__ import absolute_import, division, print_function

import fire
from pathlib import *
import time
from tqdm import tqdm

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

def ingest(dir_path, drive_ip, ext='.jpg'):
    d = Path(dir_path)
    assert d.is_dir()

    client = Client(drive_ip)
    client.connect()
    assert client.is_connected, "Failed to connect to drive"

    large_files = []

    def basic_callback(msg, cmd, value):
        """
        You can handle each callback without passing any information or data
        in from the original call.
        """
        # print("\t\tBC: received ackSeq: "+str(cmd.header.ackSequence)+\
        #             ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
        #             ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
        assert cmd.status.code == kinetic_pb2.Command.Status.SUCCESS

    try:
        client.queue_depth = 5
        client.callback_delegate = basic_callback
        tic = time.time()
        count = 0
        size = 0

        for i, p in enumerate(tqdm(filter(lambda x: x.suffix == ext, d.rglob('*')))):
            key = p.name
            with p.open('rb') as f:
                payload = f.read()
            if len(payload) > 1024*1024:
                print("{} is too large: {} Skip.".format(p, len(payload)))
                large_files.append(str(p))
                continue
            # print(i, "ingesting k={}, val=({}), {}".format(key, len(payload), p))
            client.put(key, payload, force=True, synchronization=1) # 1 - writethrough, 2 - writeback
            count += 1
            size += len(payload)

        client.wait_q(0)   
        print("Ingest {} files, {} bytes, tput {} MB/s".format(count, size, size / 1e6 / (time.time()-tic)))
        print("Success")
    finally:
        client.close()

    if large_files:
        with open('large_files.skip', 'wt') as f:
            f.write('\n'.join(large_files))

if __name__ == "__main__":
    fire.Fire()    
