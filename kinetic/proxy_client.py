from logzero import logger
import zmq

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
        self._send(key)
        return self._recv()

    def _send(self, body):
        return self._sock.send(body)
        
    def _recv(self):
        return self._sock.recv()

