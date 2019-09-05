import cv2
from logzero import logger
import numpy as np
import os
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as models


class EmDecoder(object):
    def __init__(self, target_mpixps, map_from_dir, map_to_ppm_dir, ext='jpg', init_time=time.time()):
        super(EmDecoder, self).__init__()
        self.ext = ext
        self.map_from_dir = map_from_dir
        self.map_to_ppm_dir = map_to_ppm_dir
        self.next_available_time = init_time

        sess = dbutils.get_session()
        profiles = sess.query(models.DecodeProfile) \
            .filter(models.DecodeProfile.path.like('{}%'.format(map_from_dir))) \
            .filter(models.DecodeProfile.basename.like('%.{}'.format(ext))) \
            .all()

        logger.info("Found {} decode profiles.".format(len(profiles)))
        orig_mpixps = sum([p.height * p.width / 1e6 for p in profiles]) / sum(p.decode_ms / 1e3 for p in profiles)
        self.time_scaling = orig_mpixps / target_mpixps
        logger.info("Scaling the original software decode time by {}x".format(self.time_scaling))

        # look-up table: relpath -> target decode time (s)
        self.lut = dict([os.path.relpath(p.path, map_from_dir), p.decode_ms * 1e-3 * self.time_scaling] for p in profiles)

        sess.close()

    def decode(self, arrival_time, path):
        assert path.endswith(self.ext)
        start_time = max(self.next_available_time, arrival_time)
        relpath= os.path.relpath(path, self.map_from_dir)
        ppm_path = os.path.join(self.map_to_ppm_dir, relpath).replace('.'+self.ext, '.ppm')
        arr = cv2.imread(ppm_path, cv2.IMREAD_COLOR)
        sim_elapsed = self.lut[relpath]
        # logger.debug("Map {} -> {}, expect elapsed {:.1f} ms".format(path, ppm_path, sim_elapsed*1000))
        eta = start_time + sim_elapsed
        self.next_available_time = eta
        return eta, arr


    def benchmark(self, path_list_or_generator):
        count = 0
        overdues = []

        for path in path_list_or_generator:
            count += 1
            assert path.endswith(self.ext)

            tic = time.time()
            complete_time, _ = self.decode(tic, path)
            sim_elapsed = complete_time - tic
            actual_elapsed = time.time() - tic

            if (actual_elapsed - sim_elapsed) / sim_elapsed > 0.01:  # overdue by 1%
                overdues.append((actual_elapsed - sim_elapsed) / sim_elapsed)

        logger.info("Overdue: {} / {} ({:.1f}%)".format(len(overdues), count, 100.*len(overdues) / count))
        try:
            logger.info("Overdue only: min {:.1f}%, max {:.1f}%, avg {:.1f}%".format(np.min(overdues)*100, np.max(overdues)*100, np.mean(overdues)*100))
        except:
            pass

if __name__ == '__main__':
    from s3dexp.utils import recursive_glob
    emdec = EmDecoder(300, '/mnt/hdd/fast20/jpeg/', '/mnt/ramdisk/')

    emdec.benchmark(recursive_glob('/mnt/hdd/fast20/jpeg/flickr2500', '*.jpg'))

