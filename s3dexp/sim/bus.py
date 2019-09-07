from logzero import logger
import simpy

class BusSim(object):
    def __init__(self, env, target_mbyteps):
        super(BusSim, self).__init__()
        self.target_mbyteps = float(target_mbyteps)
        self.env = env
        self._semaphore = simpy.Resource(env)

    def send(self, size_in_bytes):
        # a simpy generator
        sim_elapsed = size_in_bytes * 1e-6 / self.target_mbyteps
        with self._semaphore.request() as req:
            yield req
            yield self.env.timeout(sim_elapsed)
