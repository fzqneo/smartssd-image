from build.gen.communication_pb2 import ClientRequest, GetObjectsRequest
import logging
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

    def get_objects(self):
        request = ClientRequest()
        request.get_objects.CopyFrom(GetObjectsRequest())
        self.subscriber.send(request.SerializeToString())
        logging.debug("Received response")
