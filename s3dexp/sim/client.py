from s3dexp.sim.communication_pb2 import Request, Response
from google.protobuf.json_format import MessageToJson
import logging
import time
import zmq

class Client:
    def __init__(self, named_pipe):
        self.named_pipe = named_pipe
        self.subscriber = None
        self.listening = False

    def connect(self):
        if self.listening:
            raise Exception("Client already listening")
        context = zmq.Context()
        self.subscriber = context.socket(zmq.REQ)
        self.subscriber.connect("ipc://" + self.named_pipe)
        self.listening = True

    def close(self):
        if not self.listening:
            raise Exception("Client not listening")
        self.subscriber.close()
        self.listening = False

    def request(self, path, opcode):
        request = Request()
        request.path = path
        request.opcode = opcode
        request.timestamp = time.time()
        self.subscriber.send(request.SerializeToString())

        response = Response()
        response.ParseFromString(self.subscriber.recv())

        logging.debug("Received response %s" % MessageToJson(response))
        return response
