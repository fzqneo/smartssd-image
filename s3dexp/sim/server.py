from s3dexp.sim.communication_pb2 import Request, Response
from google.protobuf.json_format import MessageToJson
import logging
import time
import zmq


class Server:
    def __init__(self, named_pipe):
        self.named_pipe = named_pipe

    def start(self):
        logging.debug("Server listening at: %s" % self.named_pipe)
        context = zmq.Context()
        publisher = context.socket(zmq.ROUTER)
        publisher.bind("ipc://" + self.named_pipe)

        poller = zmq.Poller()
        poller.register(publisher, zmq.POLLIN)

        while True:
            #  Wait for next request from client
            events = dict(poller.poll(1000))
            if publisher in events:
                logging.debug("Received request")
                self.__parse_message(publisher)
            else:
                logging.debug("No messages received")

    def __parse_message(self, publisher):
        address, empty, data = publisher.recv_multipart()
        request = Request()
        request.ParseFromString(data)

        response = Response()
        response.request_timestamp = request.timestamp
        response.completion_timestamp = time.time()
        response.result = str(request.opcode)

        publisher.send_multipart([
            address,
            b'',
            response.SerializeToString(),
        ])
