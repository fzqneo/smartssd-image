from logzero import logger
import os
import simpy
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as models


class DecoderSim(object):
    def __init__(self, env, target_mpixps, base_dir, ext='jpg', capacity=1):
        super(DecoderSim, self).__init__()
        self.env = env
        self.ext = ext
        self.base_dir = base_dir

        self._semaphore = simpy.Resource(env, capacity=capacity)

        sess = dbutils.get_session()
        profiles = sess.query(models.DecodeProfile) \
            .filter(models.DecodeProfile.path.like('{}%'.format(base_dir))) \
            .filter(models.DecodeProfile.basename.like('%.{}'.format(ext))) \
            .all()

        logger.info("Found {} decode profiles.".format(len(profiles)))
        orig_mpixps = sum([p.height * p.width / 1e6 for p in profiles]) / sum(p.decode_ms * 1e-3 for p in profiles)
        self.time_scaling = float(orig_mpixps) / target_mpixps
        logger.info("Original {} MPix/s, target {} MPix/s,  scaling original time by {}x".format(orig_mpixps, target_mpixps, self.time_scaling))

        # assume basename is suffiently unique
        # look-up table: basename -> target decode time (s), width, height
        self.lut = {}
        for p in profiles:
            self.lut[os.path.basename(p.path)] = (p.decode_ms * 1e-3 * self.time_scaling, p.width, p.height)

        assert len(self.lut) == len(profiles)

        sess.close()
        del profiles


    def decode(self, path):
        # a simpy generator
        assert path.endswith(self.ext)
        sim_elapsed, width, height = self.lut[os.path.basename(path)]
        with self._semaphore.request() as req:
            yield req   # acquire the lock
            yield self.env.timeout(sim_elapsed)
        self.env.exit((width, height))
