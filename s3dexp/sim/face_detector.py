import json
from logzero import logger
import os
import simpy
import time

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as models


class FaceDetectorSim(object):
    def __init__(self, env, target_fps, base_dir, ext='jpg', capacity=1):
        super(FaceDetectorSim, self).__init__()
        self.env = env
        self.ext = ext
        self.base_dir = base_dir

        self._semaphore = simpy.Resource(env, capacity=capacity)

        sess = dbutils.get_session()

        profiles = sess.query(models.FaceExp) \
            .filter(models.FaceExp.path.like("{}%".format(base_dir))) \
            .filter(models.FaceExp.basename.like("%.{}".format(ext))) \
            .all()

        logger.info("Found {} face detection profiles.".format(len(profiles)))

        orig_fps = len(profiles) / sum(map(lambda p: 1e-3*(p.total_ms - p.decode_ms), profiles))

        self.time_scaling = float(orig_fps) / target_fps
        logger.info("Original {} FPS, target {} FPS,  scaling original time by {}x".format(orig_fps, target_fps, self.time_scaling))

        # assume basename is suffiently unique
        # look-up table: basename -> target face detection time (s), width, height, box
        self.lut = {}
        for p in profiles:
            self.lut[os.path.basename(p.path)] = ((p.total_ms - p.decode_ms) * 1e-3 * self.time_scaling, p.width, p.height, json.loads(p.box))

        assert len(self.lut) == len(profiles)

        sess.close()
        del profiles


    def detect_face(self, path):
        # a simpy generator
        assert path.endswith(self.ext)
        sim_elapsed, width, height, boxes = self.lut[os.path.basename(path)]
        with self._semaphore.request() as req:
            yield req   # acquire the lock
            yield self.env.timeout(sim_elapsed)
        self.env.exit(boxes)
