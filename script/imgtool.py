import fire
from logzero import logger
import os
import PIL.Image as Image

from s3dexp.utils import recursive_glob

def convert_format(src_dir, dest_dir, to_ext, from_ext="jpg"):
    assert os.path.isdir(src_dir)
    assert to_ext in ('jpg', 'png', 'ppm')
    for i, path in enumerate(recursive_glob(base_dir=src_dir, pattern="*."+from_ext)):
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


if __name__ == '__main__':
    fire.Fire()