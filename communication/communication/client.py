import zmq


class Client:
    def __init__(self, pipename):
        context = zmq.Context()
        self.subscriber = context.socket(zmq.REQ)
        self.subscriber.connect("ipc://" + pipename)

    def get_objects(self):
        self.subscriber.send_string("get_objects")
        print(self.subscriber.recv())
