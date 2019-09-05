from io import BytesIO
import os
from s3dexp.search import Filter


class SimpleReaderFilter(Filter):
    def __init__(self):
        super(SimpleReaderFilter, self).__init__()

    def __call__(self, item):
        p = item.src
        size = os.path.getsize(p)
        fd = os.open(p, os.O_RDONLY)
        buf = os.read(fd, size)
        os.close(fd)        
        item.data = buf
