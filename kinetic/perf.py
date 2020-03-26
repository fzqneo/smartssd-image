from __future__ import absolute_import, division, print_function

from collections import deque
import fire
from pathlib import *
import random
import requests
import time
import threading
from tqdm import tqdm

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType


def gets(dir_path, drive_ip, ext='.jpg', shuffle=False, queue_depth=5):
    d = Path(dir_path)
    assert d.is_dir()

    key_list = [p.name for p in filter(lambda x: x.suffix == ext, tqdm(d.rglob('*')))]
    random.shuffle(key_list) if shuffle else key_list.sort()
    print("shuffle:", shuffle)
    print("\t\n".join(key_list[:5]))

    client = Client(drive_ip)
    client.connect()
    assert client.is_connected, "Failed to connect to drive"

    tic = time.time()
    stats = {
        'count': 0,
        'size': 0
    }
 
    def basic_callback(msg, cmd, value):
        """
        You can handle each callback without passing any information or data
        in from the original call.
        """
        if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
            print("\t\tBC: received ackSeq: "+str(cmd.header.ackSequence)+\
                        ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                        ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
            raise IOError(str(StatusCodes.Name(cmd.status.code)))
        else:
            # print("\tSuccess: GET key=", str(cmd.body.keyValue.key))
            pass
        
        stats['count'] += 1
        stats['size'] += len(value)

    try:
        client.queue_depth = queue_depth
        client.callback_delegate = basic_callback

        for i, key in enumerate(tqdm(key_list)):
            # print(i, "Getting ", key)
            client.get(key)

            if i % 1000 == 0:
                count, size = stats['count'], stats['size']
                print("Get {} files, {} bytes, tput {} MB/s".format(count, size, size / 1e6 / (time.time()-tic)))
 
        client.wait_q(0)   

        count, size = stats['count'], stats['size']
        print("Get {} files, {} bytes, tput {} MB/s".format(count, size, size / 1e6 / (time.time()-tic)))
        print("Success")
    except:
        print("Issued:", i, key)
        raise
    finally:
        client.close()


def app_get(dir_path, drive_ip='localhost', port=5567, ext='.jpg', shuffle=False, num_threads=4):
    d = Path(dir_path)
    assert d.is_dir()

    key_list = [p.name for p in filter(lambda x: x.suffix == ext, tqdm(d.rglob('*')))]
    random.shuffle(key_list) if shuffle else key_list.sort()
    print("{} files. shuffle: {}".format(len(key_list), shuffle))
    print("\t\n".join(key_list[:5]))

    q = deque(key_list)

    stats = {
        'count': 0,
        'size': 0
    }
 
    def get_worker(q):
        print("\tWorker starting: {}".format(threading.current_thread().name))
        L = threading.local()
        L.count = 0
        while True:
            try:
                key = q.popleft()
                r = requests.get("http://{}:{}/get/{}".format(drive_ip, port, key))
                L.count += 1
                stats['count'] += 1
                stats['size'] += len(r.content)
                # print("{}:{}:{}".format(threading.current_thread().name, L.count, key))
            except IndexError:
                break
        print("\tWorker exiting: {}. Processed {}".format(threading.current_thread().name, L.count))

    tic = time.time()
    workers = [threading.Thread(target=get_worker, args=(q,)) for _ in range(num_threads)]
    [w.start() for w in workers]
    [w.join() for w in workers]

    count, size = stats['count'], stats['size']
    print("Get {} files, {} bytes, tput {} MB/s".format(count, size, size / 1e6 / (time.time()-tic)))
    print("Success")


if __name__ == "__main__":
    fire.Fire()    