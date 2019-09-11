from google.protobuf.json_format import MessageToJson
import logging
import logzero
from logzero import logger
import simpy
import time
import zmq

from s3dexp.sim.decoder import DecoderSim
from s3dexp.sim.bus import BusSim
from s3dexp.sim.communication_pb2 import Request, Response

OP_READONLY = 10
OP_DECODEONLY = 20
OP_READDECODE = 30
OP_DEBUG_WAIT = 500

# Simulator should run slightly ahead of real time.
# This number should be just large enough to account for computation in simulator,
# serialization overhead, and communication delay to the client,
# while not too large to avoid inaccurate simulation of requests issued earlier
RUN_AHEAD = 0.58e-3  

logzero.loglevel(logging.INFO)

# SimPy reference: https://simpy.readthedocs.io/en/latest/contents.html
class SmartStorageSim(object):
    def __init__(self, env, decoder, bus):
        super(SmartStorageSim, self).__init__()
        assert isinstance(decoder, DecoderSim)
        assert isinstance(bus, BusSim)

        # simpy environment
        self.env = env

        #  components
        self.decoder = decoder
        self.bus = bus


    def serve_request(self, request, address, callback):
        """A generator that can be passed into env.process(). 
        Calls env.process() on other components. Simulates how different components
        work together to serve a request.
        
        Arguments:
            timestamp {float} -- As returned by time.time()
            op {int} -- Op code
            request {Anything} -- Will be passed to callback when finished
            callback {function} -- Will be called callback(env.now, request) when finished
        """
        op = request.opcode
        if op == OP_DECODEONLY:
            # logger.debug("Starting to decode {} at {}".format(request.path, self.env.now))
            w,h = yield self.env.process(self.decoder.decode(request.path))
            # logger.debug("Finished decode {} at {}".format(request.path, self.env.now))
            yield self.env.process(self.bus.send(w*h*3))
        elif op == OP_DEBUG_WAIT:
            yield self.env.timeout(request.wait)
        else:
            NotImplemented

        callback(env.now, address, request)
        self.env.exit(env.now)

    
    def sched_request(self, timestamp, *args, **kwargs):
        # this is a hack, as we are not supposed to set back the simulator's internal time
        # but it should be ok to do
        self.env._now = timestamp
        self.env.process(self.serve_request(*args, **kwargs))



if __name__ == "__main__":
    base_dir = '/mnt/hdd/fast20/jpeg/flickr2500'
    ext = 'jpg'

    env = simpy.Environment(initial_time=time.time())
    decoder = DecoderSim(env, target_mpixps=140, base_dir=base_dir, capacity=4)  
    bus = BusSim(env, target_mbyteps=2000)
    ss = SmartStorageSim(env, decoder, bus)

    def on_complete(t, address, request):
        response = Response()
        response.request_timestamp = request.timestamp
        response.completion_timestamp = t
        response.value = str(request.opcode)

        publisher.send_multipart([
            address,
            b'',
            response.SerializeToString(),
        ])
        logger.debug("Sent response %s to address %s" % (MessageToJson(response), address))

    pipe_name = "/tmp/s3dexp-comm"
    context = zmq.Context()
    publisher = context.socket(zmq.ROUTER)
    publisher.bind("ipc://" + pipe_name)
    logger.info("Server listening at: %s" % pipe_name)

    poller = zmq.Poller()
    poller.register(publisher, zmq.POLLIN)

    while True:
        #  Wait for next request from client
        events = dict(poller.poll(0))
        if publisher in events:
            address, empty, data = publisher.recv_multipart()
            request = Request()
            request.ParseFromString(data)
            # assert request.timestamp < time.time(), "Reqeust from future: {} >= {}".format(request.timestamp, time.time())
            ss.sched_request(request.timestamp, request, address, on_complete)
        env.run(until=(time.time() + RUN_AHEAD))
