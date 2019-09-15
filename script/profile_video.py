import cv2
import fire
from logzero import logger
import os
import time


def decode_one_video(path):
    count_frame = 0
    width = height = None
    total_raw_size = 0

    tic = time.time()
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

    logger.info("Decode {:.2f} fps, WxH: {}x{}".format(count_frame/elapsed, width, height))


if __name__ == '__main__':
    fire.Fire()

