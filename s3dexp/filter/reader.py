from logzero import logger
import os

from s3dexp.search import Filter


class SimpleReadFilter(Filter):
    def __init__(self):
        super(SimpleReadFilter, self).__init__()

    def __call__(self, item):
        path = item.src

        size = os.path.getsize(path)
        with open(path, 'r') as f:
            fd = f.fileno()
            buf = os.read(fd, size)

        item.data = buf
        logger.debug("Read {}, {} bytes".format(path, len(item.data)))
        self.session_stats['bytes_from_disk'] += size
        return True

