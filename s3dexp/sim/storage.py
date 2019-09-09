import simpy
import time

from s3dexp.sim.decoder import DecoderSim
from s3dexp.sim.bus import BusSim
from s3dexp.sim.server import Server
from s3dexp.sim.communication_pb2 import Request, Response

OP_READONLY = 10
OP_DECODEONLY = 20
OP_READDECODE = 30
OP_DEBUG_WAIT = 500

# Simulator should run slightly ahead of real time.
# This number should be just large enough to account for computation in simulator
# and communication delay to the client,
# while not too large to avoid inaccurate simulation of requests issued earlier
RUN_AHEAD = 2e-5    # 20 microseconds.

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


    def serve_request(self, op, request, callback, path, *args, **kwargs):
        """A generator that can be passed into env.process(). 
        Calls env.process() on other components. Simulates how different components
        work together to serve a request.
        
        Arguments:
            timestamp {float} -- As returned by time.time()
            op {int} -- Op code
            request_context {Anything} -- Will be passed to callback when finished
            callback {function} -- Will be called callback(env.now, request) when finished
        """
        if op == OP_DECODEONLY:
            w,h = yield self.env.process(self.decoder.decode(path))
            yield self.env.process(self.bus.send(w*h*3))
        elif op == OP_DEBUG_WAIT:
            yield self.env.timeout(kwargs['wait'])
        else:
            NotImplemented

        callback(env.now, request)
        self.env.exit(env.now)

    
    def sched_request(self, timestamp, *args, **kwargs):
        # this is a hack, as we are not supposed to set back the simulator's internal time
        # but it should be ok to do
        self.env._now = timestamp
        self.env.process(self.serve_request(*args, **kwargs))



if __name__ == "__main__":
    from s3dexp.utils import recursive_glob
    base_dir = '/mnt/hdd/fast20/jpeg/flickr2500'
    ext = 'jpg'

    env = simpy.Environment(initial_time=time.time())
    decoder = DecoderSim(env, target_mpixps=1, base_dir=base_dir)   # still able to decode 1 image/s
    bus = BusSim(env, target_mbyteps=1)
    ss = SmartStorageSim(env, decoder, bus)

    path_gen = recursive_glob(base_dir, '*.{}'.format(ext))

    def on_complete(t, request):
        # (Haithem): send back response to client via 0MQ. Put additional info for replying in `request`.
        print "Finish on {:.6f}, request: {}".format(t, str(request))

    pipe_name = "/tmp/s3dexp-comm"
    server = Server(pipe_name)
    server.start()

    tic = time.time()
    i = 0
    while time.time() - tic < 10.:  # run for 10 sec
        # (Haithem): receive real request from 0MQ here. Should use poll.
        now = time.time()
        if now - tic > i:
            # generate a new request about every second, alternating between decode request and wait request
            if i % 2 == 0:
                path = next(path_gen)
                request = {'decode': i}
                print "Generating decode request {} {} @ {:.6f}".format(i, path, now)
                ss.sched_request(now, OP_DECODEONLY, request, on_complete, path)
            else:
                request = {'wait': i}
                print "Generating wait request {} @ {:.6f}".format(request, now)
                ss.sched_request(now, OP_DEBUG_WAIT, request, on_complete, None, wait=2)    # wait for 2 sec
            i += 1
        
        env.run(until=(time.time() + RUN_AHEAD))    # continuously keeps simulation up to real time

    # run till no events pending
    env.run()

