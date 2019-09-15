import cv2
import fire
import logging
import logzero
from logzero import logger
import numpy as np
import os
import psutil
import Queue
import threading
import time

from s3dexp.filter.object_detection import ObjectDetectionFilter
from s3dexp.search import Item
from s3dexp.utils import recursive_glob

logzero.loglevel(logging.DEBUG)

CPU_START = (18, 54)    # pin on NUMA node 1

# Specific to VIRAT + image diff + SSDMobileNet

class Context(object):
    """Shared data structure by multi threads. Don't update it too frequently."""
    def __init__(self):
        super(Context, self).__init__()
        self.lock = threading.Lock()
        self.q = Queue.Queue(300)
        self.stats = dict(
            num_items=0,
            num_workers=0,
            passed_items=0,
        )

def mse(arr1, arr2):
    # Mean Squre Error between two images
    assert isinstance(arr1, np.ndarray) and isinstance(arr2, np.ndarray)
    assert arr1.shape == arr2.shape, "{}, {}".format(arr1.shape, arr2.shape)
    return np.mean((arr1.astype(np.float) - arr2.astype(np.float))**2)


class DiffAndDetector(object):
    """Not conforming to the Filter interface"""
    def __init__(self, diff_threshold=1000., detect=False, *args, **kwargs):
        super(DiffAndDetector, self).__init__()
        self.diff_threshold = diff_threshold
        self.detect = detect
        if self.detect:
            self.detect_filter = ObjectDetectionFilter(*args, **kwargs)

        logger.info("Object detection: {}".format(self.detect))

    def __call__(self, item, reference=None):
        """Compute MSE between item.array and reference. If higer than diff_threshold, run it 
            throught object detection (if enabled).
        
        Arguments:
            item {Item} -- [description]
        
        Keyword Arguments:
            reference {ndarray} -- the reference image, must have same size and item.array. If none, will always pass item. (default: {None})
        
        Returns:
            bool -- Pass or not.
        """
        accept = (reference is None) or (mse(item.array, reference) >= self.diff_threshold)
        if accept and self.detect:
            accept = self.detect_filter(item)
        return accept


def worker(context, *args, **kwargs):
    diff_detector = DiffAndDetector(*args, **kwargs)
    count = 0
    count_accpet = 0
    while True:
        el = context.q.get()
        try:
            if el is not None:
                item, reference = el
                count += 1
                accept = diff_detector(item, reference)
                count_accpet += int(accept)
            else:
                logger.info("Worker exiting on receiving None")
                break
        except Exception as e:
            logger.exception(e)
        finally:
            context.q.task_done()
    
    with context.lock:
        context.stats['num_items'] += count
        context.stats['passed_items'] += count_accpet


def run(video_path, diff_threshold=1000., delta_frames=30, detect=False, num_workers=4):
    # expand paths
    if os.path.isfile(video_path):
        paths = [video_path]
    elif os.path.isdir(video_path):
        paths = list(recursive_glob(video_path, '*.mp4'))
    else:
        raise ValueError("Invalid: {}".format(video_path))
    logger.info("Found {} files".format(len(paths)))

    # prepare CPU affinity
    assert num_workers ==1 or num_workers % 2 == 0, "Must give an even number for num_workers or 1: {}".format(num_workers)
    if num_workers > 1:
        cpuset = range(CPU_START[0], CPU_START[0] + num_workers /2) + range(CPU_START[1], CPU_START[1] + num_workers / 2)
    else:
        cpuset = [CPU_START[0], ]
    logger.info("cpuset: {}".format(cpuset))
    psutil.Process().cpu_affinity(cpuset)

    # Setup and start workers
    context = Context()
    workers = []
    for _ in range(num_workers):
        w = threading.Thread(target=worker, args=(context, diff_threshold, detect))
        w.daemon = True
        w.start()
        workers.append(w)

    # Read and push frames
    tic = time.time()
    tic_cpu = time.clock()

    for path in paths:
        window = []
        frame_id = 0
        cap = cv2.VideoCapture(path)
        while True:
            ret, frame = cap.read()
            if ret:
                window.append(frame)
                reference = window.pop(0) if frame_id > delta_frames else None
                item = Item('{}-{}'.format(path, frame_id))
                item.array = frame
                context.q.put((item, reference))
                logger.debug("Pushed {}".format(item.src))
                frame_id += 1
            else:
                break
        cap.release()
    
    # push sentinels
    for _ in workers:
        context.q.put(None)

    logger.info("All frames pushed, waiting for queue join")
    context.q.join()

    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu
    
    vals_dict={
        'num_items': context.stats['num_items'],
        'avg_wall_ms': 1e3 * elapsed / context.stats['num_items'],
        'avg_cpu_ms': 1e3 * elapsed_cpu / context.stats['num_items'],
        'avg_mbyteps': -1,  # TODO
    }
        
    logger.info(str(vals_dict))



if __name__ == '__main__':
    fire.Fire(run)