import fire
from google.protobuf.json_format import MessageToJson
import json
import logging
import logzero
from logzero import logger
import simpy
import time
import zmq

from s3dexp.sim.communication_pb2 import Request, Response
from s3dexp.sim.bus import BusSim
from s3dexp.sim.decoder import DecoderSim, VideoDecoderSim
from s3dexp.sim.face_detector import FaceDetectorSim

OP_READONLY = 10
OP_DECODEONLY = 20
OP_READDECODE = 30
OP_DECODE_FACE = 40
OP_DECODE_VIDEO = 50
OP_DEBUG_WAIT = 500

# Simulator should run slightly ahead of real time.
# This number should be just large enough to account for computation in simulator,
# serialization overhead, and communication delay to the client,
# while not too large to avoid inaccurate simulation of requests issued earlier
RUN_AHEAD = 0.58e-3  

logzero.loglevel(logging.INFO)

# SimPy reference: https://simpy.readthedocs.io/en/latest/contents.html
class SmartStorageSim(object):
    def __init__(self, env, decoder, bus, face_detector, video_decoder):
        super(SmartStorageSim, self).__init__()
        assert isinstance(decoder, DecoderSim)
        assert isinstance(bus, BusSim)

        # simpy environment
        self.env = env

        #  components
        self.decoder = decoder
        self.bus = bus
        self.face_detector = face_detector
        self.video_decoder = video_decoder

    def serve_request(self, request, address, callback):
        """A generator that can be passed into env.process(). 
        Calls env.process() on other components. Simulates how different components
        work together to serve a request.
        
        Arguments:
            timestamp {float} -- As returned by time.time()
            op {int} -- Op code
            request {Anything} -- Will be passed to callback when finished
            callback {function} -- Will be called callback(env.now, request, value) when finished
        """
        op = request.opcode
        if request.value:
            payload = json.loads(request.value)
        retval = {'op': op}

        if op == OP_DECODEONLY:
            # logger.debug("Starting to decode {} at {}".format(request.path, self.env.now))
            w,h = yield self.env.process(self.decoder.decode(request.path))
            # logger.debug("Finished decode {} at {}".format(request.path, self.env.now))
            yield self.env.process(self.bus.send(w*h*3))

        elif op == OP_DECODE_FACE:
            w,h = yield self.env.process(self.decoder.decode(request.path))
            boxes = yield self.env.process(self.face_detector.detect_face(request.path))
            # assume we only transmitted the cropped patches
            transmitted_size = sum(map(lambda b: abs(3*(b[0]-b[2])*(b[1]-b[3])), boxes))
            yield self.env.process(self.bus.send(transmitted_size))
            retval['face_boxes'] = boxes

        elif op == OP_DECODE_VIDEO: # only use for one stream
            frame_id = payload['frame_id']
            w,h = yield self.env.process(self.video_decoder.decode_frame(request.path, frame_id)) 
            yield self.env.process(self.bus.send(w*h*3))

        elif op == OP_DEBUG_WAIT:
            yield self.env.timeout(request.wait)
        else:
            NotImplemented

        callback(self.env.now, address, request, retval)
        self.env.exit(self.env.now)

    
    def sched_request(self, timestamp, *args, **kwargs):
        # this is a hack, as we are not supposed to set back the simulator's internal time
        # but it should be ok to do
        self.env._now = timestamp
        self.env.process(self.serve_request(*args, **kwargs))


def run_server(
    base_dir = '/mnt/hdd/fast20/jpeg/flickr50k', ext='jpg', 
    decoder_mpixps=140., num_decoder=5, bus_mbyteps=2000, face_fps=30., video_fps=120., 
    run_ahead=RUN_AHEAD, verbose=False):

    if verbose:
        logzero.loglevel(logging.DEBUG)

    logger.info("Run ahead = {:.2f} ms".format(1000*run_ahead))

    env = simpy.Environment(initial_time=time.time())
    decoder = DecoderSim(env, target_mpixps=decoder_mpixps, base_dir=base_dir, capacity=num_decoder)  
    bus = BusSim(env, target_mbyteps=bus_mbyteps)
    face_detector = FaceDetectorSim(env, target_fps=face_fps, base_dir=base_dir)
    video_decoder = VideoDecoderSim(env, target_fps=video_fps)
    ss = SmartStorageSim(env, decoder, bus, face_detector, video_decoder)

    def on_complete(t, address, request, value):
        response = Response()
        response.request_timestamp = request.timestamp
        response.completion_timestamp = t
        response.value = json.dumps(value)

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

    logger.info("======READY")

    while True:
        #  Wait for next request from client
        events = dict(poller.poll(0))
        if publisher in events:
            address, empty, data = publisher.recv_multipart()
            request = Request()
            request.ParseFromString(data)
            logger.debug("Recv request from %s: %s" % (address, MessageToJson(request)))
            # assert request.timestamp < time.time(), "Request from future: {} >= {}".format(request.timestamp, time.time())
            ss.sched_request(request.timestamp, request, address, on_complete)
        env.run(until=(time.time() + run_ahead))

if __name__ == '__main__':
    fire.Fire(run_server)