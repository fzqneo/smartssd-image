from logzero import logger
import os
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as models


class DecoderSim(object):
    def __init__(self, target_mpixps, base_dir, ext='jpg', init_time=time.time()):
        super(DecoderSim, self).__init__()
        self.ext = ext
        self.base_dir = base_dir
        self.next_available_time = init_time

        sess = dbutils.get_session()
        profiles = sess.query(models.DecodeProfile) \
            .filter(models.DecodeProfile.path.like('{}%'.format(base_dir))) \
            .filter(models.DecodeProfile.basename.like('%.{}'.format(ext))) \
            .all()

        logger.info("Found {} decode profiles.".format(len(profiles)))
        orig_mpixps = sum([p.height * p.width / 1e6 for p in profiles]) / sum(p.decode_ms * 1e-3 for p in profiles)
        self.time_scaling = orig_mpixps / target_mpixps
        logger.info("Original {} MPix/s, target {} MPix/s,  scaling original time by {}x".format(orig_mpixps, target_mpixps, self.time_scaling))

        # look-up table: path -> target decode time (s)
        self.lut = dict([(p.path, p.decode_ms * 1e-3 * self.time_scaling) for p in profiles])

        sess.close()
        del profiles

    def decode(self, arrival_time, path):
        assert path.endswith(self.ext)
        start_time = max(self.next_available_time, arrival_time)
        sim_elapsed = self.lut[path]
        # logger.debug("Map {} -> {}, expect elapsed {:.1f} ms".format(path, ppm_path, sim_elapsed*1000))
        finish_time = start_time + sim_elapsed
        self.next_available_time = finish_time
        return finish_time
