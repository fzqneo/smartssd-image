import cv2
import fire
from logzero import logger
import multiprocessing as mp
import numpy as np
import os
import PIL.Image as Image
import random
import time

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as models
from s3dexp.utils import recursive_glob


def _get_meta(path):
    size = os.path.getsize(path)
    img = Image.open(path)
    width, height = img.width, img.height
    format = img.format
    return (path, format, size, width, height)


def image_meta(base_dir, ext='jpg', num_workers=16):
    sess = dbutils.get_session()
    
    pool = mp.Pool(num_workers)

    for path, format, size, width, height in pool.imap(_get_meta, recursive_glob(base_dir, '*.{}'.format(ext)), 64):
        dbutils.insert_or_update_one(
            sess, models.ImageMeta,
            {'path': path},
            {'format': format, 'size': size, 'width': width, 'height': height}
        )

        logger.info("Read {}".format(path))

    sess.commit()
    sess.close()

    
def disk_read(base_dir, disk, ext='jpg', sort_inode=False, store_result=True):
    logger.warn("Make sure you cleaned the OS page buffer!")
    base_dir = os.path.realpath(base_dir)
    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))

    if sort_inode:
        paths = sorted(paths, key=lambda p: os.stat(p).st_ino)
        logger.info("Sort by inode num.")
    else:
        # deterministic pseudo-random
        random.seed(42)
        random.shuffle(paths)

    results = []

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

        results.append({
            'keys_dict': {'path': p, 'disk': disk},
            'vals_dict': vals_dict
        })


    if store_result:
        logger.info("Going to write {} results to DB".format(len(results)))
        sess = dbutils.get_session()
        for r in results:
            dbutils.insert_or_update_one(
                sess, models.DiskReadProfile,
                keys_dict=r['keys_dict'],
                vals_dict=r['vals_dict']
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

        keys_dict={'path': path, 'hostname': this_hostname}
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
