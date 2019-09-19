import cv2
from logzero import logger
import os
import simpy
import time

from s3dexp import this_hostname
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
            .filter(models.DecodeProfile.hostname=='cloudlet029') \
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


class VideoDecoderSim(object):
    def __init__(self, env, target_fps, capacity=1):
        """A "stateful" decoder that only works for one video at a time. Keep tracks of the "current" frame
        and can skip frames forward."""
        super(VideoDecoderSim, self).__init__()
        self.env = env
        self.target_fps = target_fps
        self._semaphore = simpy.Resource(env, capacity=capacity)
        self.current_path = None
        self.current_frame_id = None
        self.video_frames = None
        self.h = self.w = None
        logger.info("Created VideoDecoderSim at {} FPS".format(self.target_fps))

    def decode_frame(self, path, frame_id):
        """Assume the client is sending increasing frame_id so we can skip frames here"""
        if self.current_path != path:
            # open once to get h,w
            self.current_path = path
            self.current_frame_id = 0
            cap = cv2.VideoCapture(path)
            self.w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            self.h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info("Initiating new video WxH {}x{} {}".format(self.w, self.h, path))
            cap.release()
            
        assert frame_id >= self.current_frame_id

        sim_elapsed = (1. / self.target_fps) * (frame_id - self.current_frame_id)
        logger.debug("VideoDecoderSim: decoding {} frames, {:.2f} ms".format((frame_id - self.current_frame_id), sim_elapsed*1000))
        with self._semaphore.request() as req:
            yield req
            yield self.env.timeout(sim_elapsed)
            self.current_frame_id = frame_id    # fast-forward
        
        self.env.exit((self.w, self.h))