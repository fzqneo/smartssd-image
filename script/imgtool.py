import os
import random
import shutil

import cv2
import fire
from logzero import logger
import numpy as np 
import pathlib2 as pathlib
# import PIL.Image as Image
from tqdm import tqdm

from s3dexp.utils import recursive_glob

def convert_format(src_dir, dest_dir, to_ext='.ppm', from_ext=".jpg"):
    assert to_ext in ('.jpg', '.png', '.ppm', '.npy')

    src_dir = pathlib.Path(src_dir).resolve()
    dest_dir = pathlib.Path(dest_dir)   # may not exist

    for ipath in filter(lambda p: p.suffix==from_ext, tqdm(src_dir.rglob('*'))):
        opath = (dest_dir / ipath.relative_to(src_dir)).with_suffix(to_ext)
        opath.parent.mkdir(parents=True, exist_ok=True)

        # convert and save
        arr = cv2.imread(str(ipath), cv2.IMREAD_COLOR)
        if to_ext == '.npy':
            np.save(opath, arr)
        else:
            cv2.imwrite(opath, arr)

def sample_dir(src_dir, dest_dir, num, ext='.jpg', ):
    """Sampling `num` files from src_dir and save them to dest_dir.
    Preserve relative paths.
    
    Arguments:
        src_dir {[type]} -- [description]
        dest_dir {[type]} -- [description]
        num {[type]} -- [description]
    
    Keyword Arguments:
        ext {str} -- [description] (default: {'.jpg'})
    """
    src_dir = pathlib.Path(src_dir).resolve()
    dest_dir = pathlib.Path(dest_dir)   # may not exist

    paths = list(filter(lambda p: p.suffix==ext, src_dir.rglob('*')))
    random.seed(1234)
    sample_paths = random.sample(paths, num)
    logger.info("Sampled {} from {}".format(len(sample_paths), len(paths)))

    for ip in tqdm(sample_paths):
        op = dest_dir / ip.relative_to(src_dir)
        op.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(ip), str(op))


if __name__ == '__main__':
    fire.Fire()