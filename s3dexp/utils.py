import cv2
import fnmatch
import os

from s3dexp.fiemap import fiemap2, FIEMAP_FLAG_SYNC

def recursive_glob(base_dir, pattern):
    for root, _, filenames in os.walk(base_dir):
        for filename in fnmatch.filter(filenames, pattern):
            yield os.path.join(root, filename)


def get_fie_physical_start(path):
    with open(path, 'r') as f:
        mappings_gen = fiemap2(f, 0, 1024, flags=FIEMAP_FLAG_SYNC)
        first_rec = next(mappings_gen)
        physical_start = first_rec.physical
        del mappings_gen
    return physical_start

def get_num_video_frames(path):
    cap = cv2.VideoCapture(path)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return int(frames)