import collections
import fire
import flask
import logging
from logzero import logger
import multiprocessing as mp
import threading
from Queue import Queue

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

logger.setLevel(logging.INFO)

app = flask.Flask(__name__)

USE_MP = True

# use shared memory for result writeback
MAX_PAYLOAD_LEN = 1024*1024
MAX_SLOT_NUM = 16
# Each slot has (len, payload), which are shared memory data.
# .len also used as a semaphore
SM_Slot = collections.namedtuple('SM_Slot', ['len', 'payload']) # len=-1 is unset, len=0 is unsuccessful
sm_slots = [SM_Slot(len=mp.Value('l', -1), payload=mp.Array('c', MAX_PAYLOAD_LEN, lock=False)) for _ in range(MAX_SLOT_NUM)]
sm_available_idx = set(range(MAX_SLOT_NUM)) # slot idx that are available to use; shared by flask threads

requests = mp.Queue() if USE_MP else Queue() # shared by worker and flask threads

def serve_requests(drive_ip, requests, sm_slots):
    client = Client(drive_ip)
    client.connect()
    assert client.is_connected, "Failed to connect to drive"
    logger.info("[{}] kv_client connected {}".format(mp.current_process().pid, drive_ip))
    client.queue_depth = 16
    
    def data_callback(key, sm_idx):
        """
        You can pass in any mutable object (such as a dictionary or list) to
        store/share information between threads or you can pass in information
        for each command issued (such as a start time) for special handling
        in the callback.
        """
        def wrapper(msg, cmd, value):
            slot = sm_slots[sm_idx]
            if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
                logger.error("\t\tkey:" + key +
                            ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
                            ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                            ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
                slot.len.value = 0
            else:
                logger.debug("\tSuccess: GET key={}".format(key))
                # assert isinstance(value, bytearray)
                vlen = len(value)
                slot.payload[:vlen] = buffer(value) # avoid copy
                slot.len.value = vlen # must set len last because requester polls it to check completion
                
        return wrapper

    while True:
        key, sm_idx = requests.get()
        client.callback_delegate = data_callback(key, sm_idx)
        client.get(key)


@app.route('/ping')
def ping():
    return "pong"


@app.route('/get/<key>')
def get(key):
    key = bytes(key)
    sm_idx = sm_available_idx.pop()
    logger.debug("[{}] key {}, sm_idx {}".format(threading.current_thread().name, key, sm_idx))
    requests.put((key, sm_idx))

    slot = sm_slots[sm_idx]
    try:
        while slot.len.value < 0:
            continue
        plen = slot.len.value
        if plen == 0:
            logger.warn("Unsuccessful key: {}".format(key))
            payload = b''
        else:
            payload = bytes(buffer(slot.payload, 0, plen)) # have to make a copy because we're releasing the slot
        return payload
    finally:
        slot.len.value = -1
        sm_available_idx.add(sm_idx)


@app.route('/emget/<key>/<float:wait>/<int:size>')
def emget(key, wait, size):
    """Emulated get on active disks"""
    raise NotImplementedError()


def main(drive_ip, port=5567, kv_processes=2):

    if USE_MP:
        for i in range(kv_processes):
            serve_thread = mp.Process(target=serve_requests, args=(drive_ip, requests, sm_slots,), name='kv-thread-%d' % i)
            serve_thread.daemon = True
            serve_thread.start()
    else:
        serve_thread = threading.Thread(target=serve_requests, args=(drive_ip, requests, sm_slots,), name='kv-thread')
        serve_thread.daemon = True
        serve_thread.start()

    app.run(host='0.0.0.0', port=port, threaded=True)


if __name__ == "__main__":
    fire.Fire(main)


"""
HTTP is obviously the overhead?
(at 16 requesters we can max out the disk, but not 8)

2515 total size = 190985009
50628 total size = 3808977505 (excluding 1 large file)
"""