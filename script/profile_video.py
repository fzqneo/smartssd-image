import cv2
import fire
from logzero import logger
import numpy as np
import os
import time


def decode_one_video(path):
    count_frame = 0
    width = height = None
    total_raw_size = 0

    tic = time.time()
    tic_cpu = time.clock()

    cap = cv2.VideoCapture(path)
    while cap.isOpened():
        ret, frame = cap.read()
        if ret:
            height, width = frame.shape[:2]
            total_raw_size += frame.size
            count_frame += 1
            # logger.debug("Get {} frames, {} {}".format(count_frame, width, height))
        else:
            break

    cap.release()
    
    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu

    logger.info("Decode {:.2f} fps, WxH: {}x{}, CPU time {:.3f} ms per frame".format(count_frame/elapsed, width, height, 1000.*elapsed_cpu/count_frame))


def mse(arr1, arr2):
    # Mean Squre Error between two images
    assert isinstance(arr1, np.ndarray) and isinstance(arr2, np.ndarray)
    assert arr1.shape == arr2.shape, "{}, {}".format(arr1.shape, arr2.shape)
    # return np.mean((arr1.astype(np.float) - arr2.astype(np.float))**2)

    sum_squared_error = 0.
    X_CHUNKSIZE = 4    # empirically chose. Too small -> high GIL overhead. Too large -> large memory writes.
    for x in range(0, arr1.shape[0], X_CHUNKSIZE):
        sum_squared_error += np.sum((arr1[x:x+X_CHUNKSIZE,:,:].astype(np.float) - arr2[x:x+X_CHUNKSIZE,:,:].astype(np.float))**2)
    return sum_squared_error / arr1.size


def time_MSE(size=(1280, 720), repeat=100):
    img1 = np.random.randint(256, size=list(size) + [3], dtype=np.uint8)
    img2 = np.random.randint(256, size=list(size) + [3], dtype=np.uint8)

    tic = time.time()
    tic_cpu = time.clock()
    for r in range(repeat):
        _ = mse(img1, img2)

    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu
    logger.info("Wall {:.3f} ms/call, CPU {:.3f} ms/call".format(1000*elapsed/repeat, 1000*elapsed_cpu/repeat))


if __name__ == '__main__':
    fire.Fire()

