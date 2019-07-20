import cv2
import directio
import fire
import fnmatch
import glob
from itertools import islice
import json
import logging
from logzero import logger
import numpy as np
import os
from rgb_histo import calc_1d_hist_flatten
import time

logger.setLevel(logging.DEBUG)

def _directio_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    content = directio.read(fd, 1024*1024)  # FIXME
    os.close(fd)
    return content

def _recursive_glob(base_dir, pattern):
    for root, dirnames, filenames in os.walk(base_dir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def minidiamond(base_dir, pattern="*.jpg", limit=None, fetcher_only=False):
    """Speed test for Scopelist + Fetcher + RGB
    
    Arguments:
        base_dir {string} -- Base directory to find files
    
    Keyword Arguments:
        pattern {str} -- File name pattern (default: {"*.jpg"})
        limit {integer} -- Stop after (default: {None})
        fetcher_only -- only run fetcher (default: {False})
    """
    from opendiamond.filter import Session
    from minidiamond import ATTR_OBJ_ID
    from minidiamond.scopelist import FolderScopeList
    from minidiamond.filter.fil_fetcher import Fetcher
    from minidiamond.filter.fil_rgb import RGBFilter

    info = {}    
    scopelist = FolderScopeList(base_dir, pattern)
    session = Session('filter')

    filters = []
    filters.append(Fetcher(args=[], blob=None, session=session))
    if not fetcher_only:
        filters.append(RGBFilter(args=[], blob=None, session=session))
    logger.info("Running filters: {}".format(map(type, filters)))

    count_raw_bytes = 0
    tic = time.time()
    for i, obj in enumerate(islice(scopelist, 0, limit)):
        map(lambda fil: fil(obj), filters)
        count_raw_bytes += len(obj.data)
        # logger.debug('{}: {} bytes'.format(obj[ATTR_OBJ_ID], len(obj.data)))
        if not fetcher_only:
            logger.debug('{}: {} cols(w) {} rows(h)'.format(
                obj[ATTR_OBJ_ID], obj.get_int('_cols.int'), obj.get_int('_rows.int')))

    toc = time.time()

    count = i + 1
    logger.info("Found {} files".format(count))

    info['image_count'] = count
    info['total_MBytes'] = count_raw_bytes / 1.0e6
    info['tput_image'] = count / (toc - tic)
    info['tput_Mbytes'] = (count_raw_bytes / 1.0e6) / (toc - tic)

    print json.dumps(info, indent=4, sort_keys=True)


def read_file(image_dir, pattern='*.jpg', limit=None, standalone=True):
    """Speed test reading files from a directory.
    
    Arguments:
        image_dir {string} -- Directory path
    
    Keyword Arguments:
        pattern {str} -- File name pattern (default: {'*.jpg'})
        limit {integer} -- Read at most this many (default: {None})
        standalone {bool} -- Called as a stanadlone test, or as a step in a pipeline (default: {True})
    
    Returns:
        [type] -- [description]
    """
    
    info = {}
    raw_bytes = list()
    count = 0
    count_raw_bytes = 0

    # read file
    logger.info("Read raw bytes")
    tic = time.time()
    for p in _recursive_glob(image_dir, pattern):
        count += 1

        # b = _directio_read(p)
        # if not standalone:
        #     raw_bytes.append(b)
        # count_raw_bytes += len(b)

        with open(p, 'r') as f:
            b = f.read()
            if not standalone:
                raw_bytes.append(b)
            count_raw_bytes += len(b)

        if limit is not None and count >= limit:
            break
    toc = time.time()
    info['image_count'] = count
    info['total_MBytes'] = count_raw_bytes / 1.0e6
    info['read_tput'] = count / (toc - tic)
    info['read_tput_Mbytes'] = (count_raw_bytes / 1.0e6) / (toc - tic)
    logger.info("Found {} files".format(count))

    if standalone:
        print json.dumps(info, indent=4, sort_keys=True)
        return None
    else:
        return info, raw_bytes


def raw_rgb_histo(image_dir, pattern='*.jpg', limit=None):

    info, raw_bytes = read_file(image_dir, pattern, limit=limit, standalone=False)
    count = info['image_count']

    decoded_images = list()

    # decode jpeg
    logger.info("Image decode")
    tic = time.time()
    for i, b in enumerate(raw_bytes):
        im = cv2.imdecode(np.frombuffer(b, np.int8), cv2.IMREAD_COLOR)
        decoded_images.append(im)
        # logger.debug('Decoding {}: {}'.format(i, im.shape))
    toc = time.time()
    info['decode_tput'] = count / (toc - tic)

    del raw_bytes

    # rgb histogram
    logger.info("RGB histo")
    tic = time.time()
    for im in decoded_images:
        hist = calc_1d_hist_flatten(im)
        assert hist.shape == (256*3, 1)
    toc = time.time()
    info['rgb_histo_tput'] = count / (toc - tic)

    print json.dumps(info, indent=4, sort_keys=True)


if __name__ == "__main__":
    fire.Fire()    
