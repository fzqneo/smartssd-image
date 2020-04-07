from collections import deque, namedtuple
import fire
from google.protobuf.json_format import MessageToJson
import logging
from logzero import logger
import Queue
import zmq

logger.setLevel(logging.INFO)

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

# local
from proxy_pb2 import Message

# def handle_get(address, req_msg, kvclient, q):
#     key = req_msg.key

#     def data_callbak(msg, cmd, value):
#         if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
#             logger.error("\t Key: " +  str(cmd.body.keyValue.key) + \
#                         ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
#                         ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
#                         ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
#             value = b''
#         else:
#             logger.debug("[get] Success: GET " + str(cmd.body.keyValue.key))
    
#         q.put((address, value))
#     kvclient.callback_delegate = data_callbak
#     kvclient.get(key)


def main(drive_ip, port=5567, verbose=False):
    if verbose:
        logger.setLevel(logging.DEBUG)

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

    # use these to avoid redefining the callback function every time
    # assumption: there are no requests for the same key in near future (no collision)
    pending_requests = dict() # key -> [address, source proxy message, value]
    ready_requests = dict() # same

    def data_callbak(msg, cmd, value):
        # fills the value in pending requests and move it to ready_requests
        key = bytes(cmd.body.keyValue.key)
        if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
            logger.error("\t Key: " +  str(cmd.body.keyValue.key) + \
                        ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
                        ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                        ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
            value = b''
        else:
            logger.debug("[get] Success: GET " + str(cmd.body.keyValue.key))
            value = value

        t = pending_requests.pop(key)
        t[2] = bytes(value)
        ready_requests[key] = t

    kvclient.callback_delegate = data_callbak

    while True:
        #  Wait for next request from client
        events = poller.poll(0)
        if events:
            address, _, body = router.recv_multipart()
            proxy_msg = Message()
            proxy_msg.ParseFromString(body)

            logger.debug("Recv request from {}, opcode {}".format(address, str(proxy_msg.opcode)))

            if proxy_msg.opcode == Message.Opcode.PING: # trivial
                resp_msg = Message()
                resp_msg.value = b'PONG'
                router.send_multipart([address, b'', resp_msg.SerializeToString()])

            elif proxy_msg.opcode in (Message.Opcode.GET, Message.Opcode.GETSMART):
                key = proxy_msg.key
                pending_requests[key] = [address, proxy_msg, None]
                kvclient.get(key)

            else:
                raise NotImplementedError

        # send response
        if ready_requests:
            key, (address, req_msg, value) = ready_requests.popitem()
            resp_msg = Message()
            resp_msg.key = key
            resp_msg.opcode = req_msg.opcode

            if req_msg.opcode == Message.Opcode.GET:
                resp_msg.value = value
            elif req_msg.opcode == Message.Opcode.GETSMART:
                resp_msg.value = b'\0' * req_msg.size
            else:
                raise ValueError("Other opcode should not land here: " + str(req_msg.opcode))

            # logger.debug("Replying to {}: {}".format(address, MessageToJson(resp_msg)))
            router.send_multipart([address, b'', resp_msg.SerializeToString()])



if __name__ == "__main__":
    fire.Fire(main)