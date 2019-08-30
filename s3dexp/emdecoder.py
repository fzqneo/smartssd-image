import cv2
from logzero import logger
import numpy as np
from operator import itemgetter, attrgetter
import os
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as models


class EmDecoder(object):
    def __init__(self, mpixps, base_dir, ppm_dir, dataset, ext='jpg'):
        super(EmDecoder, self).__init__()
        self.ext = ext
        self.base_dir = base_dir
        self.ppm_dir = ppm_dir

        sess = dbutils.get_session()
        profiles = sess.query(models.DecodeProfile) \
            .filter(models.DecodeProfile.path.like('%{}%'.format(dataset))) \
            .filter(models.DecodeProfile.basename.like('%.{}'.format(ext))) \
            .all()

        logger.info("Found {} decode profiles.".format(len(profiles)))
        orig_mpixps = sum([p.height * p.width / 1e6 for p in profiles]) / sum(p.decode_ms / 1e3 for p in profiles)
        self.time_scaling = orig_mpixps / mpixps
        logger.info("Scaling the original software decode time by {}x".format(self.time_scaling))

        # look-up table: relpath -> target decode time
        self.lut = dict([os.path.relpath(p.path, base_dir), p.decode_ms * self.time_scaling] for p in profiles)

        sess.close()

    def __call__(self, path):
        """Returns a numpy array
        
        Arguments:
            path {[type]} -- [description]
        """
        assert path.endswith(self.ext)
        tic = time.time()
        relpath= os.path.relpath(path, self.base_dir)
        ppm_path = os.path.join(self.ppm_dir, relpath).replace('.'+self.ext, '.ppm')
        expect_ms = self.lut[relpath]
        logger.debug("Map {} -> {}, expect {} ms".format(path, ppm_path, expect_ms))
        arr = cv2.imread(ppm_path, cv2.IMREAD_COLOR)

        elapsed = time.time() - tic
        # logger.debug("Elapsed {} ms".format(elapsed*1000))
        slack_time = expect_ms / 1000 - elapsed
        if slack_time > 1e-5 :
            # logger.debug("Sleeping {} ms ".format(slack_time * 1000))
            time.sleep(slack_time * 0.8)
        else:
            pass
            # logger.warn("Overdue time budget: expect {} ms, elapsed {} ms".format(expect_ms, elapsed * 1000))
        return arr

    def benchmark(self, path_list_or_generator):
        l_expect_ms = []
        l_actual_ms = []
        count = 0

        for path in path_list_or_generator:
            count += 1
            assert path.endswith(self.ext)

            relpath= os.path.relpath(path, self.base_dir)
            expect_ms = self.lut[relpath]

            tic = time.time()
            _ = self(path)
            actual_ms = 1000 * (time.time() - tic)

            logger.debug("{}, expect {} ms, elapsed {} ms".format(path, expect_ms, actual_ms))

            l_expect_ms.append(expect_ms)
            l_actual_ms.append(actual_ms)

        assert count == len(l_expect_ms) == len(l_actual_ms)

        l_expect_ms = np.array(l_expect_ms)
        l_actual_ms = np.array(l_actual_ms)
        l_error_ratio = (l_actual_ms - l_expect_ms) / l_expect_ms

        logger.info("Error ratio range {:1f}% -- {:1f}%".format(100*np.min(l_error_ratio), 100*np.max(l_error_ratio)))
        logger.info("Mean abs error ratio {:.1f}%".format(100*np.mean(np.abs(l_error_ratio))))
        logger.info("Mean signed error ms {}".format(np.mean(l_actual_ms - l_expect_ms)))
        logger.info("Overdue {} / {} ({:1f}%)".format(np.count_nonzero((l_error_ratio > 1.05)), count,  np.count_nonzero((l_error_ratio > 1.05)) /count))


if __name__ == '__main__':
    from s3dexp.utils import recursive_glob
    emdec = EmDecoder(300, '/mnt/hdd/fast20/jpeg/', '/mnt/ramdisk/', 'flickr2500')

    emdec.benchmark(recursive_glob('/mnt/hdd/fast20/jpeg/flickr2500', '*.jpg'))

