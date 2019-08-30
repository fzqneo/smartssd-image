from build.gen.communication_pb2 import ClientRequest
from google.protobuf.json_format import MessageToJson
import logging
import threading
import zmq


class Server:
    def __init__(self, named_pipe):
        self.named_pipe = named_pipe
        self.should_listen = False
        self.thread = None

    def start(self):
        if self.should_listen:
            raise Exception("Server already started")
        self.should_listen = True
        self.thread = threading.Thread(target=self.__start_inner)
        self.thread.start()

    def stop(self):
        if not self.should_listen:
            raise Exception("Server not started")
        self.should_listen = False
        self.thread.join()

    def __start_inner(self):
        logging.debug("Server listening to named pipe: %s" % self.named_pipe)
        context = zmq.Context()
        publisher = context.socket(zmq.REP)
        publisher.bind("ipc://" + self.named_pipe)

        poller = zmq.Poller()
        poller.register(publisher, zmq.POLLIN)

        while self.should_listen:
            #  Wait for next request from client
            events = dict(poller.poll(1000))
            if publisher in events:
                logging.debug("Received request")
                self.__parse_message(publisher)
            else:
                logging.debug("No messages received")

        logging.debug("Server shutting down")

    def __parse_message(self, publisher):
        request = ClientRequest()
        request.ParseFromString(publisher.recv())
        if request.HasField("get_objects"):
            publisher.send(b"objects")
        else:
            raise Exception("Unrecognized message type: %s" % MessageToJson(request))