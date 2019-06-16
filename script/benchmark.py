import cv2
import fire
import fnmatch
import glob
import json
from logzero import logger
import os
from rgb_histo import calc_1d_hist_flatten
import time


def _recursive_glob(base_dir, pattern):
    for root, dirnames, filenames in os.walk(base_dir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def rgb_histo(image_dir, pattern='*.jpg', limit=None):
    info = {}
    decoded_images = list()
    count = 0

    # decode jpeg
    logger.info("Image decode")
    tic = time.time()
    for p in _recursive_glob(image_dir, pattern):
        count += 1
        im = cv2.imread(p)
        decoded_images.append(im)
        # logger.debug('Decoding {}: {}'.format(p, im.shape))
        if limit is not None and count >= limit:
            break
    toc = time.time()
    info['image_count'] = count
    info['decode_throughput'] = count / (toc - tic)
    logger.info("Found {} images".format(count))

    # rgb histogram
    logger.info("RGB histo")
    tic = time.time()
    for im in decoded_images:
        hist = calc_1d_hist_flatten(im)
        assert hist.shape == (256*3, 1)
    toc = time.time()
    info['rgb_histo_throughput'] = count / (toc - tic)

    print json.dumps(info, indent=4)


if __name__ == "__main__":
    fire.Fire()    
