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
        time_scale = orig_mpixps / mpixps
        logger.info("Scaling the original software decode time by {}x".format(time_scale))

        # look-up table: relpath -> target decoding 
        self.lut = dict([os.path.relpath(p.path, base_dir), p.decode_ms * time_scale] for p in profiles)

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
        if slack_time > 0 :
            logger.debug("Sleeping {} ms ".format(slack_time * 1000))
            time.sleep(slack_time * 0.9)
        else:
            logger.warn("Overdue time budget: expect {} ms, elapsed {} ms".format(expect_ms, elapsed * 1000))
        return arr

    def benchmark(self, path_list_or_generator):
        error_ratio = []
        error_ms = []
        count_overdue = 0
        count = 0

        for path in path_list_or_generator:
            count += 1
            assert path.endswith(self.ext)
            tic = time.time()
            relpath= os.path.relpath(path, self.base_dir)
            ppm_path = os.path.join(self.ppm_dir, relpath).replace('.'+self.ext, '.ppm')
            expect_ms = self.lut[relpath]
            logger.debug("Map {} -> {}, expect {} ms".format(path, ppm_path, expect_ms))
            _ = cv2.imread(ppm_path, cv2.IMREAD_COLOR)

            elapsed = time.time() - tic
            # logger.debug("Elapsed {} ms".format(elapsed*1000))
            slack_time = expect_ms / 1000 - elapsed
            if slack_time > 0 :
                logger.debug("Sleeping {} ms ".format(slack_time * 1000))
                time.sleep(slack_time * 0.8)    # empirical
            else:
                logger.warn("Overrun time budget: expect {} ms, elapsed {} ms".format(expect_ms, elapsed * 1000))
                count_overdue += 1

            e2e_ms = 1000 * (time.time() - tic)
            error_ms = abs(e2e_ms - expect_ms)
            error_ratio = error_ms / expect_ms

        logger.info("Mean error ratio {:.3f}%".format(np.mean(100*error_ratio)))
        logger.info("Mean error ms {}".format(np.mean(error_ms)))
        logger.info("Overdue {} / {}".format(count_overdue, count))


if __name__ == '__main__':
    from s3dexp.utils import recursive_glob
    emdec = EmDecoder(200, '/mnt/hdd/fast20/jpeg/', '/mnt/ramdisk/', 'flickr2500')

    emdec.benchmark(recursive_glob('/mnt/hdd/fast20/jpeg/flickr2500', '*.jpg'))

    # tic = time.time()
    # arr = emdec('/mnt/hdd/fast20/jpeg/flickr2500/00ad32a02aa3978b4cb6b4a3435992ba2936d8d4.jpg')
    # print(type(arr))
    # print(arr.shape)
    # print("Elapsed {} ms".format((time.time()-tic)*1000))
