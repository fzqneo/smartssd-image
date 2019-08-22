import cv2
import fire
from logzero import logger
import numpy as np
import os
import PIL.Image as Image
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as models
from s3dexp.utils import recursive_glob


def image_meta(base_dir, ext='jpg'):
    sess = dbutils.get_session()

    for path in recursive_glob(base_dir, '*.{}'.format(ext)):
        size = os.path.getsize(path)
        img = Image.open(path)
        width, height = img.width, img.height
        format = img.format
        dbutils.insert_or_update_one(
            sess, models.ImageMeta,
            {'path': path},
            {'format': format, 'size': size, 'width': width, 'height': height}
        )

        logger.info("Read {}".format(path))

    sess.commit()
    sess.close()

    
def disk_read(base_dir, disk, ext='jpg', sort_inode=False):
    logger.warn("Make sure you cleaned the OS page buffer!")
    base_dir = os.path.realpath(base_dir)

    sess = dbutils.get_session()
    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))

    if sort_inode:
        paths = sorted(paths, key=lambda p: os.stat(p).st_ino)
        logger.info("Sort by inode num.")

    for p in paths:
        tic = time.time()

        fd = os.open(p, os.O_RDONLY)
        size = os.path.getsize(p)
        buf = os.read(fd, size)
        os.close(fd)        
        elapsed = time.time() - tic

        logger.debug("{}: {} bytes {} ms".format(p, len(buf), elapsed * 1000))
        vals_dict = {'size': size}
        if sort_inode:
            vals_dict['seq_read_ms'] = elapsed * 1000
        else:
            vals_dict['rand_read_ms'] = elapsed * 1000

        dbutils.insert_or_update_one(
            sess, models.DiskReadProfile,
            keys_dict={'path': p, 'disk': disk},
            vals_dict=vals_dict
        )

    sess.commit()
    sess.close()


def decode_time(base_dir, ext='jpg', repeat=3):
    sess = dbutils.get_session()

    for path in recursive_glob(base_dir, '*.{}'.format(ext)):
        with open(path, 'rb') as f:
            buf = f.read()

        tic = time.time()
        for _ in range(repeat):
            arr = cv2.imdecode(np.frombuffer(buf, np.int8), cv2.IMREAD_COLOR)

        elapsed = time.time() - tic

        h, w = arr.shape[:2]
        decode_ms = elapsed*1000 / repeat
        size = len(buf)

        keys_dict={'path': path}
        vals_dict={
            'basename': os.path.basename(path),
            'size': size,
            'height': h,
            'width': w,
            'decode_ms': decode_ms
        }
        logger.debug(str(vals_dict))

        dbutils.insert_or_update_one(
            sess, models.DecodeProfile,
            keys_dict=keys_dict,
            vals_dict=vals_dict
        )

    sess.commit()
    sess.close()


if __name__ == '__main__':
    fire.Fire()
