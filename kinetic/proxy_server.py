from collections import deque
import fire
import logging
from logzero import logger
import Queue
import zmq

logger.setLevel(logging.DEBUG)

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

def handle_get(address, body, kvclient, q):

    key = body

    def wrapper(msg, cmd, value):
        if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
            logger.error("\t\tkey:" + key +
                        ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
                        ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                        ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
            value = b''
        else:
            logger.debug("[get] Success: GET key={}".format(key))
        
        q.put((address, value))

    kvclient.callback_delegate = wrapper
    kvclient.get(key)


def main(drive_ip, port=5567):
    context = zmq.Context()
    router = context.socket(zmq.ROUTER)
    router.bind("tcp://*:{}".format(port))
    logger.info("Listening on port {}".format(port))

    poller = zmq.Poller()
    poller.register(router, zmq.POLLIN)
    
    kvclient = Client(drive_ip)
    kvclient.connect()
    assert kvclient.is_connected, "Failed to connect to drive"
    logger.info("kv_client connected {}".format(drive_ip))
    kvclient.queue_depth = 16

    q = Queue.Queue()
    
    while True:
        #  Wait for next request from client
        events = dict(poller.poll(0))
        if router in events:
            address, _, body = router.recv_multipart()
            logger.debug("Recv request from " + address)
            # enque kv request and add call back
            handle_get(address, body, kvclient, q)

        try:
            address, body = q.get_nowait()
            router.send_multipart([address, b'', body])
            logger.debug("Replying " + address)
        except Queue.Empty:
            pass


if __name__ == "__main__":
    fire.Fire(main)