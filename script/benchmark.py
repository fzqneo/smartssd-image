import cv2
import fire
import fnmatch
import glob
import json
from logzero import logger
import numpy as np
import os
from rgb_histo import calc_1d_hist_flatten
import time


def _recursive_glob(base_dir, pattern):
    for root, dirnames, filenames in os.walk(base_dir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)

def read_file(image_dir, pattern='*.jpg', limit=None, print_result=True):
    info = {}
    raw_bytes = list()
    count = 0
    count_raw_bytes = 0

    # read file
    logger.info("Read raw bytes")
    tic = time.time()
    for p in _recursive_glob(image_dir, pattern):
        count += 1
        with open(p, 'r') as f:
            b = f.read()
            raw_bytes.append(b)
            count_raw_bytes += len(b)
        if limit is not None and count >= limit:
            break
    toc = time.time()
    info['image_count'] = count
    info['read_throughput'] = count / (toc - tic)
    info['read_throughput_Mbytes'] = (count_raw_bytes / 1.0e6) / (toc - tic)
    logger.info("Found {} files".format(count))

    if print_result:
        print json.dumps(info, indent=4, sort_keys=True)
        return None
    else:
        return info


def rgb_histo(image_dir, pattern='*.jpg', limit=None):
    info = {}
    raw_bytes = list()
    decoded_images = list()
    count = 0
    count_raw_bytes = 0

    # read file
    logger.info("Read raw bytes")
    tic = time.time()
    for p in _recursive_glob(image_dir, pattern):
        count += 1
        with open(p, 'r') as f:
            b = f.read()
            raw_bytes.append(b)
            count_raw_bytes += len(b)
        if limit is not None and count >= limit:
            break
    toc = time.time()
    info['image_count'] = count
    info['read_throughput'] = count / (toc - tic)
    info['read_throughput_Mbytes'] = (count_raw_bytes / 1.0e6) / (toc - tic)
    logger.info("Found {} images".format(count))

    # decode jpeg
    logger.info("Image decode")
    tic = time.time()
    for i, b in enumerate(raw_bytes):
        im = cv2.imdecode(np.frombuffer(b, np.int8), cv2.IMREAD_COLOR)
        decoded_images.append(im)
        # logger.debug('Decoding {}: {}'.format(i, im.shape))
    toc = time.time()
    info['decode_throughput'] = count / (toc - tic)

    del raw_bytes

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
