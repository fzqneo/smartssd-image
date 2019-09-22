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

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.filter.object_detection import ObjectDetectionFilter
from s3dexp.search import Item
from s3dexp.sim.client import SmartStorageClient
from s3dexp.utils import recursive_glob, get_num_video_frames

logzero.loglevel(logging.INFO)

CPU_START = (18, 54)    # pin on NUMA node 1

# Specialized to VIRAT + image diff + SSDMobileNet


class Context(object):
    """Shared data structure by multi threads. Don't update it too frequently."""
    def __init__(self):
        super(Context, self).__init__()
        self.lock = threading.Lock()
        self.q = Queue.Queue(30)
        self.stats = dict(
            num_items=0,
            num_workers=0,
            passed_items=0,
            bytes_from_disk=0,
        )

def mse(arr1, arr2):
    # Mean Squre Error between two images
    assert isinstance(arr1, np.ndarray) and isinstance(arr2, np.ndarray)
    assert arr1.shape == arr2.shape, "{}, {}".format(arr1.shape, arr2.shape)
    # return np.mean((arr1.astype(np.float) - arr2.astype(np.float))**2)

    sum_squared_error = 0.
    X_CHUNKSIZE = 40    # empirically chose. Too small -> high GIL overhead. Too large -> large memory writes.
    for x in range(0, arr1.shape[0], X_CHUNKSIZE):
        sum_squared_error += np.sum((arr1[x:x+X_CHUNKSIZE,:,:].astype(np.float) - arr2[x:x+X_CHUNKSIZE,:,:].astype(np.float))**2)
    return sum_squared_error / arr1.size


class DiffAndDetector(object):
    """NOT conforming to the Filter interface"""
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
    count_accept = 0
    while True:
        el = context.q.get()
        try:
            if el is not None:
                item, reference = el
                count += 1
                accept = diff_detector(item, reference)
                count_accept += int(accept)

                if accept:
                    logger.debug("Accepted {}".format(item.src))
            else:
                logger.info("Worker exiting on receiving None")
                break
        except Exception as e:
            logger.exception(e)
        finally:
            context.q.task_done()
    
    logger.info("Thread: num_items: {}, passed_items {}".format(count, count_accept))
    with context.lock:
        context.stats['num_items'] += count
        context.stats['passed_items'] += count_accept


def cv2_decoder(path, context, every=1):
    cap = cv2.VideoCapture(path)
    frame_id = 0
    while True:
        ret, frame = cap.read()
        if ret:
            if frame_id % every == 0:
                yield frame, frame_id
            frame_id += 1
            continue
        else:
            break
    cap.release()
    context.stats['bytes_from_disk'] += os.path.getsize(path)


def smart_decoder(ss_client, path, context, every=1):
    
    num_frames = get_num_video_frames(path)
    for frame_id in range(0, num_frames, every):
        arr = ss_client.decode_video(path, frame_id)
        context.stats['bytes_from_disk'] += arr.size
        yield arr, frame_id


# Use FasterRCNN+ResNet for detection. These video are wide-angle. MobileNet doesn't work well.
def run(
    video_path='/mnt/hdd/fast20/video/VIRAT/mp4/VIRAT_S_000200_02_000479_000635.mp4', diff_threshold=100., delta_frames=30, every_frame=10, 
    detect=False, confidence=0.95, num_workers=4, smart=False, expname=None, verbose=False):
    """Run NoScope's frame skipping + image difference detection on videos. Optionally, pass passing frames to a DNN object detector.
    
    Keyword Arguments:
        video_path {str} -- Path of a video or directory of videos 
        diff_threshold {float} -- For the diff detector to fire (default: {1000.})
        delta_frames {int} -- For diff detector: compare with the frame delta_frames ago (default: {30})
        detect {bool} -- If true, run DNN on passing frames (default: {False})
        every_frame {int} -- For frame skipping, run diff detector every `every_frame` (default: {1})
        num_workers {int} -- Parallel workers (default: {4})
        smart {bool} -- Use smart disk or not (default: {False})
        expname {[type]} -- If not None, will store to DB with expname (default: {None})
    
    Raises:
        ValueError: [description]
    """

    if verbose:
        logzero.loglevel(logging.DEBUG)

    # expand paths
    if os.path.isfile(video_path):
        paths = [video_path]
    elif os.path.isdir(video_path):
        paths = list(recursive_glob(video_path, '*.mp4'))
    else:
        raise ValueError("Invalid: {}".format(video_path))
    logger.info("Found {} files".format(len(paths)))

    # set CPU affinity
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
        w = threading.Thread(target=worker, args=(context, diff_threshold, detect), kwargs={'targets': ['person',], 'confidence': confidence}) # search for persons
        w.daemon = True
        w.start()
        workers.append(w)

    # Exclude preload time from measurement
    if smart:
        ss_client = SmartStorageClient(map_from_dir='/mnt/hdd/fast20/video/VIRAT/mp4', preload=True)

    tic = time.time()
    tic_cpu = time.clock()
    total_frames = 0

    for path in paths:
        num_frames = get_num_video_frames(path)
        logger.info("Processing {} with {} frames".format(path, num_frames))
        window = []

        if smart:
            gen = smart_decoder(ss_client, path, context, every_frame)
        else:
            gen = cv2_decoder(path, context, every_frame)

        for i, (frame, frame_id) in enumerate(gen):
            window.append(frame)
            reference = window.pop(0) if frame_id > delta_frames else None
            item = Item('{}-{}'.format(path, frame_id))
            item.array = frame
            context.q.put((item, reference))
            logger.debug("Pushed {}".format(item.src))
            if frame_id % 100 == 0:
                logger.info("Procssed {} frames, frame id {}, {}".format(i, frame_id, path))

        total_frames += num_frames
    
    # push sentinels
    for _ in workers:
        context.q.put(None)

    logger.info("All frames pushed, waiting for queue join")
    context.q.join()
    for w in workers:
        w.join()

    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu
    
    logger.info("Elapsed {:.2f} s, Elapsed CPU {:.2f} s".format(elapsed, elapsed_cpu))
    logger.info(str(context.stats))
    logger.info("Total frames: {}".format(total_frames))

    keys_dict={'expname': expname, 'basedir': str(video_path), 'ext': 'video', 'num_workers': num_workers, 'hostname': this_hostname}
    vals_dict={
                    'num_items': total_frames,  # different from image because we have frame skipping
                    'avg_wall_ms': 1e3 * elapsed / total_frames,
                    'avg_cpu_ms': 1e3 * elapsed_cpu / total_frames,
                    'avg_mbyteps': context.stats['bytes_from_disk'] * 1e-6 / elapsed,
                }

    logger.info(str(keys_dict))
    logger.info(str(vals_dict))

    if expname is not None:
        sess = dbutils.get_session()
        dbutils.insert_or_update_one(
            sess, 
            dbmodles.EurekaExp,
            keys_dict=keys_dict,
            vals_dict=vals_dict)
        sess.commit()
        sess.close()


if __name__ == '__main__':
    fire.Fire(run)