from __future__ import absolute_import, division, print_function

from collections import deque
import fire
import functools
from logzero import logger
import multiprocessing as mp
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


def gets(dir_path, drive_ip, ext='.jpg', shuffle=False, queue_depth=16):
    """Similar to shenzi/perf/Gets but get keys based on a real directory.
    Uses a single kv_client in the main process. 
    
    Arguments:
        dir_path {[type]} -- [description]
        drive_ip {[type]} -- [description]
    
    Keyword Arguments:
        ext {str} -- [description] (default: {'.jpg'})
        shuffle {bool} -- [description] (default: {False})
        queue_depth {int} -- [description] (default: {16})
    
    Raises:
        IOError: [description]
    """
    d = Path(dir_path)
    assert d.is_dir()

    key_list = [p.name for p in filter(lambda x: x.suffix == ext, tqdm(d.rglob('*')))]
    random.shuffle(key_list) if shuffle else key_list.sort()
    print("shuffle:", shuffle)
    print("\t\n".join(key_list[:5]))

    client = Client(drive_ip)
    client.connect()
    assert client.is_connected, "Failed to connect to drive " + drive_ip

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
                toc = time.time()
                count, size = stats['count'], stats['size']
                print("Get {} files, {} bytes, tput {} file/s, {} MB/s".format(count, size, count / (toc-tic), size / 1e6 / (toc-tic)))
 
        client.wait_q(0)   

        count, size = stats['count'], stats['size']
        toc = time.time()
        print("Get {} files, {} bytes, tput {} file/s, {} MB/s".format(count, size, count / (toc-tic), size / 1e6 / (toc -tic)))
        print("Success")
    except:
        print("Issued:", i, key)
        raise
    finally:
        client.close()



def _proxy_get_fn(drive_ip, getsize, key_list):
    import proxy_client
    import itertools
    pclient = proxy_client.KineticProxyClient(drive_ip)
    pclient.connect()
    count = 0
    size = 0
    print("Working on {} keys".format(len(key_list)))
    if getsize is None:
        map_fn = pclient.get
    else:
        map_fn = functools.partial(pclient.get_smart, size=getsize)

    for res in itertools.imap(map_fn, key_list):
        count += 1
        size += len(res)
        if count % 100 == 0:
            print("[{}] worked {} keys".format(mp.current_process().pid, count))
    pclient.close()
    return (count, size)

def proxy_get(dir_path, drive_ip="localhost", num_threads=4, getsize=None, shuffle=False, ext=".jpg"):
    d = Path(dir_path)
    assert d.is_dir()

    key_list = [p.name for p in filter(lambda x: x.suffix == ext, tqdm(d.rglob('*')))]
    random.shuffle(key_list) if shuffle else key_list.sort()
    print("{} files. shuffle: {}".format(len(key_list), shuffle))
    print("\t\n".join(key_list[:5]))

    tic = time.time()
    pool = mp.Pool(num_threads)
    sublists = [list(key_list[i::num_threads]) for i in range(num_threads)]
    stats = pool.map(functools.partial(_proxy_get_fn, drive_ip, getsize), sublists)
    pool.close()
    toc = time.time()

    count, size = [sum(x) for x in zip(*stats)]        
    print("Get {} files, {} bytes, tput {} file/s, {} MB/s".format(
        count, size, count / (toc-tic), size / 1e6 / (toc -tic)))
    assert count == len(key_list)


def app_get(dir_path, drive_ip='localhost', port=5567, ext='.jpg', shuffle=False, num_threads=4):
    """GET perf test using our web app. Multiprocessing is used to maximize throughput.
    
    Arguments:
        dir_path {[type]} -- [description]
    
    Keyword Arguments:
        drive_ip {str} -- [description] (default: {'localhost'})
        port {int} -- [description] (default: {5567})
        ext {str} -- [description] (default: {'.jpg'})
        shuffle {bool} -- [description] (default: {False})
        num_threads {int} -- [description] (default: {4})
    """
    d = Path(dir_path)
    assert d.is_dir()

    key_list = [p.name for p in filter(lambda x: x.suffix == ext, tqdm(d.rglob('*')))]
    random.shuffle(key_list) if shuffle else key_list.sort()
    print("{} files. shuffle: {}".format(len(key_list), shuffle))
    print("\t\n".join(key_list[:5]))

    q = mp.JoinableQueue(100)

    stats_lock = mp.Lock()
    stats = mp.Manager().dict({
        'count': 0,
        'size': 0
    })
 
    def get_worker(q):
        print("[{}, {}] Worker starts".format(mp.current_process().pid, threading.current_thread().name))
        L = threading.local()
        L.count = 0
        L.size = 0
        while True:
            key = q.get()
            if key is None:
                q.task_done()
                break
            r = requests.get("http://{}:{}/get/{}".format(drive_ip, port, key))
            L.count += 1
            L.size += len(r.content)
            q.task_done()
            # print("{}:{}:{}".format(threading.current_thread().name, L.count, key))
        with stats_lock:
            stats['count'] += L.count
            stats['size'] += L.size
        print("[{}, {}] Worker exiting. Processed {}".format(mp.current_process().pid, threading.current_thread().name, L.count))

    tic = time.time()
    # workers = [threading.Thread(target=get_worker, args=(q,), name='worker-%d' % i) for i in range(num_threads)]
    workers = [mp.Process(target=get_worker, args=(q,), name='worker-%d' % i) for i in range(num_threads)]
    [w.start() for w in workers]
    for k in tqdm(key_list):
        q.put(k)
    [q.put(None) for w in workers]
    q.join()
    [w.join() for w in workers]

    count, size = stats['count'], stats['size']
    toc = time.time()
    print("Get {} files, {} bytes, tput {} file/s, {} MB/s".format(count, size, count / (toc-tic), size / 1e6 / (toc -tic)))
    assert count == len(key_list)


def app_getchunk(drive_ip='localhost', port=5567, num_threads=4, chunksize=1000000, repeat=1000):
    """GET dummpy chunk perf test using our web app. 
    No kv operations.
    Multiprocessing is used to maximize throughput.
    
    Arguments:
    
    Keyword Arguments:
        drive_ip {str} -- [description] (default: {'localhost'})
        port {int} -- [description] (default: {5567})
        num_threads {int} -- [description] (default: {4})
        chunksize {int} -- chunk size in bytes
        repeat {int} -- how many times in each worker
    """

    stats_lock = mp.Lock()
    stats = mp.Manager().dict({
        'count': 0,
        'size': 0
    })
 
    def work_fn(chunksize, repeat):
        print("[{}, {}] Worker starts".format(mp.current_process().pid, threading.current_thread().name))
        L = threading.local()
        L.count = 0
        L.size = 0
        for _ in range(repeat):
            r = requests.get("http://{}:{}/debug/getchunk/{}".format(drive_ip, port, chunksize))
            L.count += 1
            L.size += len(r.content)
        with stats_lock:
            stats['count'] += L.count
            stats['size'] += L.size
        print("[{}, {}] Worker exiting. Processed {}".format(mp.current_process().pid, threading.current_thread().name, L.count))

    tic = time.time()
    # workers = [threading.Thread(target=get_worker, args=(q,), name='worker-%d' % i) for i in range(num_threads)]
    workers = [mp.Process(target=work_fn, args=(chunksize, repeat), name='worker-%d' % i) for i in range(num_threads)]
    [w.start() for w in workers]
    [w.join() for w in workers]

    count, size = stats['count'], stats['size']
    toc = time.time()
    print("Get {} files, {} bytes, tput {} file/s, {} MB/s".format(count, size, count / (toc-tic), size / 1e6 / (toc -tic)))
    assert count == num_threads * repeat
    assert size == count * chunksize

if __name__ == "__main__":
    fire.Fire()    