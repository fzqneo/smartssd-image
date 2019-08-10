import cv2
import fire
from io import BytesIO
from itertools import islice
import json
import logging
from logzero import logger
import multiprocessing as mp
import numpy as np
import os
import PIL.Image as Image
import Queue
from rgb_histo import calc_1d_hist_flatten
import threading
import time

from s3dexp.utils import recursive_glob


if int(os.getenv('VERBOSE', 0)) >= 1:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


def minidiamond(base_dir, pattern="*.*", limit=None, fetcher_only=False, async_fetcher=True, use_mp=False):
    """Speed test for Scopelist + Fetcher + RGB
    
    Arguments:
        base_dir {string} -- Base directory to find files
    
    Keyword Arguments:
        pattern {str} -- File name pattern (default: {"*.jpg"})
        limit {integer} -- Stop after (default: {None})
        fetcher_only -- only run fetcher (default: {False})
        async_fetcher {bool} -- run fetcher in a separate thread/process (default: {True})
        use_mp {bool} -- use multi-processing instead of multithreading (default: {False})
    """
    from opendiamond.filter import Session
    from minidiamond import ATTR_OBJ_ID
    from minidiamond.scopelist import FolderScopeList
    from minidiamond.filter.fil_fetcher import Fetcher
    from minidiamond.filter.fil_rgb import RGBFilter, RGBFilter_PIL

    info = {}    
    scopelist = FolderScopeList(base_dir, pattern)
    session = Session('filter')

    fetcher = Fetcher(args=[], blob=None, session=session)
    filters = []
    if not fetcher_only:
        filters.append(RGBFilter(args=[], blob=None, session=session))
    logger.info("Running filters: {}".format(map(type, [fetcher] + filters)))

    count_raw_bytes = 0
    tic = time.time()
    count = 0

    if async_fetcher:
        # pipeline fetcher and other filters
        def do_fetcher(scopelist, q):
            count = 0
            logger.info("[{}] fetcher running".format(os.getpid()))
            for obj in islice(scopelist, 0, limit):
                count += 1
                fetcher(obj)
                q.put(obj)
                logger.debug("({}) enqued {}".format(count, obj[ATTR_OBJ_ID]))
            q.put(None) # sentinel
            logger.info("ScopeList ends.")
        
        # switch between threading and multiprocessing
        if use_mp:
            queue_cls = mp.Queue
            thread_cls = mp.Process
        else:
            queue_cls = Queue.Queue
            thread_cls = threading.Thread
        
        logger.info("Using {} and {} for async".format(queue_cls, thread_cls))

        q = queue_cls(maxsize=100)
        fetcher_worker = thread_cls(target=do_fetcher, args=(scopelist, q))
        
        fetcher_worker.start()

        logger.info("[{}] filters running".format(os.getpid()))
        while True:
            obj = q.get()
            if obj is not None:
                count += 1
                count_raw_bytes += len(obj.data)
                try:
                    map(lambda fil: fil(obj), filters)
                    if not fetcher_only:
                        logger.debug('({}) {}: {} cols(w) {} rows(h)'.format(
                            count, obj[ATTR_OBJ_ID], obj.get_int('_cols.int'), obj.get_int('_rows.int')))
                except:
                    logger.error('Error happend at {}-th. {}'.format(count, obj[ATTR_OBJ_ID]))
            else:
                break

        fetcher_worker.join()
    else:
        for i, obj in enumerate(islice(scopelist, 0, limit)):
            count += 1
            try:
                fetcher(obj)
                count_raw_bytes += len(obj.data)
                map(lambda fil: fil(obj), filters)
                # logger.debug('{}: {} bytes'.format(obj[ATTR_OBJ_ID], len(obj.data)))
                if not fetcher_only:
                    logger.debug('{}: {} cols(w) {} rows(h)'.format(
                        obj[ATTR_OBJ_ID], obj.get_int('_cols.int'), obj.get_int('_rows.int')))
            except:
                logger.error('Error happend at {}-th. {}'.format(i, obj[ATTR_OBJ_ID]))
    
    toc = time.time()

    logger.info("Found {} files".format(count))

    info['image_count'] = count
    info['total_MBytes'] = count_raw_bytes / 1.0e6
    info['tput_image'] = count / (toc - tic)
    info['tput_Mbytes'] = (count_raw_bytes / 1.0e6) / (toc - tic)

    print json.dumps(info, indent=4, sort_keys=True)


def read_file(image_dir, pattern='*.*', limit=None, standalone=True):
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
    for p in recursive_glob(image_dir, pattern):
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
    info['total_MBytes'] = count_raw_bytes / (2.**20)
    info['read_tput'] = count / (toc - tic)
    info['read_tput_Mbytes'] = (count_raw_bytes / 2.0**20) / (toc - tic)
    logger.info("Found {} files".format(count))

    if standalone:
        print json.dumps(info, indent=4, sort_keys=True)
        return None
    else:
        return info, raw_bytes



def raw_decode(image_dir, pattern='*.*', codec='CV2', limit=None):
    assert codec in ('PIL', 'CV2', 'TurboJPEG')

    info, raw_bytes = read_file(image_dir, pattern, limit=limit, standalone=False)
    count = info['image_count']

    decoded_images = list()
    logger.info("Using codec {}".format(codec))

    # decode jpeg
    logger.info("Image decode")
    tic = time.time()
    for i, b in enumerate(raw_bytes):
        if codec == 'PIL':
            im = np.array(Image.open(BytesIO(b)))
        elif codec == 'CV2':
            im = cv2.imdecode(np.frombuffer(b, np.int8), cv2.IMREAD_COLOR)
        elif codec == 'TurboJPEG':
            raise NotImplementedError

        logger.debug('Decoding {}: {}'.format(i, im.shape))
        decoded_images.append(im)
    toc = time.time()
    info['decode_tput'] = count / (toc - tic)

    del raw_bytes
    print json.dumps(info, indent=4, sort_keys=True)



def raw_rgb_histo(image_dir, pattern='*.jpg', limit=None):

    info, raw_bytes = read_file(image_dir, pattern, limit=limit, standalone=False)
    count = info['image_count']

    decoded_images = list()

    # decode jpeg
    logger.info("Image decode")
    tic = time.time()
    for i, b in enumerate(raw_bytes):
        # im = cv2.imdecode(np.frombuffer(b, np.int8), cv2.IMREAD_COLOR)
        im = np.array(Image.open(BytesIO(b)))
        decoded_images.append(im)
        # logger.debug('Decoding {}: {}'.format(i, im.shape))
    toc = time.time()
    info['decode_tput'] = count / (toc - tic)

    del raw_bytes

    # rgb histogram
    # logger.info("RGB histo")
    # tic = time.time()
    # for im in decoded_images:
    #     hist = calc_1d_hist_flatten(im)
    #     assert hist.shape == (256*3, 1)
    # toc = time.time()
    # info['rgb_histo_tput'] = count / (toc - tic)

    print json.dumps(info, indent=4, sort_keys=True)


if __name__ == "__main__":
    fire.Fire()    
