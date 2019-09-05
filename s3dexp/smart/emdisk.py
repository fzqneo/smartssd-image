import os
import time

class EmDiskInterface(object):
    def get(self, arrival_time, path):
        raise NotImplementedError


class RealDisk(EmDiskInterface):
    def get(self, arrival_time, path):
        tic = time.time()
        fd = os.open(path, os.O_RDONLY)
        size = os.path.getsize(path)
        buf = os.read(fd, size)
        os.close(fd)
        elapsed = time.time() - tic
        return arrival_time + elapsed, buf


class EmDiskSim(EmDiskInterface):
    def get(self, arrival_time, path):
        raise NotImplementedError