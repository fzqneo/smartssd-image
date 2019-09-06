from logzero import logger
import os

from s3dexp.search import Filter


class SimpleReadFilter(Filter):
    def __init__(self):
        super(SimpleReadFilter, self).__init__()

    def __call__(self, item):
        p = item.src
        size = os.path.getsize(p)
        fd = os.open(p, os.O_RDONLY)
        buf = os.read(fd, size)
        os.close(fd)        
        item.data = buf
        logger.debug("Read {}, {} bytes".format(p, len(item.data)))

