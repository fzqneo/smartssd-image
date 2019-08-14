import fire
from logzero import logger
import os
import PIL.Image as Image
import s3dexp.db.utils as dbutils
import s3dexp.db.models as models
from s3dexp.utils import recursive_glob
import time

def image_meta(base_dir, ext='jpg'):
    sess = dbutils.get_session()

    for path in recursive_glob(base_dir, '*.{}'.format(ext)):
        size = os.path.getsize(path)
        img = Image.open(path)
        width, height = img.width, img.height
        format = img.format
        dbutils.insert_or_update_one(
            sess, models.ImageMeta,
            {'path': path},
            {'format': format, 'size': size, 'width': width, 'height': height}
        )

        logger.info("Read {}".format(path))

    sess.commit()
    sess.close()

    
def disk_read(base_dir, ext='jpg', disk='hdd'):
    print "Make sure you cleaned the OS page buffer!"

    sess = dbutils.get_session()
    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))
    for p in paths:
        tic = time.time()
        # with open(p, 'rb') as f:
        #     buf = f.read()

        fd = os.open(p, os.O_RDONLY)
        buf = os.read(fd, os.path.getsize(p))
        os.close(fd)
        
        elapsed = time.time() - tic
        logger.info("{}: {} bytes {} ms".format(p, len(buf), elapsed * 1000))
        dbutils.insert_or_update_one(
            sess, models.DiskReadProfile,
            {'path': p},
            {'disk': disk, 'rand_read_ms': elapsed * 1000}
        )

    sess.commit()
    sess.close()


if __name__ == '__main__':
    fire.Fire()
