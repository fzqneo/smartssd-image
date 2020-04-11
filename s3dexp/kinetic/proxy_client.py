from __future__ import absolute_import, division, print_function

from logzero import logger
import zmq

# local
from s3dexp.kinetic.proxy_pb2 import Message

class KineticProxyClient(object):
    def __init__(self, host='localhost', port=5567):
        super(KineticProxyClient, self).__init__()
        self.host = host
        self.port = port

    def connect(self):
        context = zmq.Context()
        req = context.socket(zmq.REQ)
        dest = 'tcp://{}:{}'.format(self.host, self.port)
        req.connect(dest)
        self._context = context
        self._sock = req
        logger.info("Connected to {}".format(dest))

    def close(self):
        self._sock.close()

    def get(self, key):
        req_msg = Message()
        req_msg.opcode = Message.Opcode.GET
        req_msg.key = key

        self._send_msg(req_msg)
        resp_msg = self._recv_msg(Message)
        return resp_msg.value

    def get_smart(self, key, size):
        req_msg = Message()
        req_msg.opcode = Message.Opcode.GETSMART
        req_msg.key = key
        req_msg.size = size
        self._send_msg(req_msg)
        return self._recv_msg(Message).value

    def _send_msg(self, msg):
        self._send(msg.SerializeToString())

    def _recv_msg(self, msg_cls):
        msg = msg_cls()
        msg.ParseFromString(self._recv())
        return msg

    def _send(self, body):
        return self._sock.send(body)
        
    def _recv(self):
        return self._sock.recv()

