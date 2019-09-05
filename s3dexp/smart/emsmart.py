from logzero import logger
from s3dexp.em.emcpu import ProcessDilator
from s3dexp.em.emdecoder import EmDecoder
from s3dexp.em.emdisk import EmDiskInterface
import time


class EmSmartStorage(object):
    def __init__(self, dilator, emdecoder, emdisk):
        super(EmSmartStorage, self).__init__()
        assert isinstance(dilator, ProcessDilator)
        assert isinstance(emdecoder, EmDecoder)
        assert isinstance(emdisk, EmDiskInterface)
        
        self.dilator = dilator
        self.emdecoder = emdecoder
        self.emdisk = emdisk


    def get(self, arrival_time, path):
        return self.emdisk.get(arrival_time, path)

    def get_decode(self, arrival_time, path):
        disk_rct, _ = self.emdisk.get(arrival_time, path)
        decode_rct, arr = self.emdecoder.decode(disk_rct, path)
        return decode_rct, arr

    def get_paths(self, arrival_time, list_path, hint='sort'):
        assert hint in ('sort', 'random')
        raise NotImplementedError


class LocalClient(object):
    def __init__(self, emsmartstorage):
        super(LocalClient, self).__init__()
        assert isinstance(emsmartstorage, EmSmartStorage)
        self.ss = emsmartstorage

    def _wait_till(self, t):
        slack = t - time.time()
        if slack > 1e-4:
            logger.debug("Sleeping for {:.1f} ms".format(slack*1000))
            time.sleep(slack)
        elif slack <  -1e-4:
            logger.warn("Too late by {:.2f} ms".format(-slack*1000))
        return

    def get(self, *args, **kwargs):
        rct, buf = self.ss.get(time.time(), *args, **kwargs)
        self._wait_till(rct)
        return buf

    def get_decode(self, *args, **kwargs):
        rct, arr = self.ss.get_decode(time.time(), *args, **kwargs)
        self._wait_till(rct)
        return arr
