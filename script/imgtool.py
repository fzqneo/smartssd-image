import os
import random
import shutil

import fire
from logzero import logger
import pathlib2 as pathlib
import PIL.Image as Image
from tqdm import tqdm

from s3dexp.utils import recursive_glob

def convert_format(src_dir, dest_dir, to_ext='ppm', from_ext="jpg"):
    assert os.path.isdir(src_dir)
    assert to_ext in ('jpg', 'png', 'ppm')
    for i, path in enumerate(tqdm(recursive_glob(base_dir=src_dir, pattern="*."+from_ext))):
        # mapped directory
        dest_path = os.path.join(
            dest_dir,
            os.path.relpath(path, src_dir)
        )
        # map extension
        dest_path = os.path.splitext(dest_path)[0] + ".{}".format(to_ext)

        logger.debug("[{}] Converting {} to {}".format(i, path, dest_path))
        assert not os.path.exists(dest_path), "Converted file alreay exists!"

        # create intermediate directory
        if not os.path.exists(os.path.dirname(dest_path)):
            os.makedirs(os.path.dirname(dest_path))

        # convert and save
        im = Image.open(path)
        im.save(dest_path)


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