from logzero import logger
import math
import time

class ProcessDilator(object):
    """Dilate the in-process computation between reset() and wait()
    in order to emulate the elapsed time on a lower GHz processor.
    """
    
    def __init__(self, target_ghz, platform_ghz=3.0):
        super(ProcessDilator, self).__init__()
        assert 0 < target_ghz < platform_ghz
        self._scaling = platform_ghz / target_ghz
        self._tic = time.clock()
        logger.info("Dilator scale factor: {}".format(self._scaling))

    def reset(self):
        self._tic = time.clock()

    def wait(self):
        elapsed = time.clock() - self._tic
        expect = elapsed * self._scaling
        x = time.time()
        while time.clock() - self._tic < expect:
            for _ in range(100):
                x = math.sqrt(x)
        return


if __name__ == '__main__':
    dilator = ProcessDilator(target_ghz=1.)

    import random
    l = list(range(1000000))
    random.shuffle(l)
    tic = time.time()
    l.sort()
    elapsed = time.time() - tic
    print("Full speed: {:.1f}ms".format(elapsed*1000))

    random.shuffle(l)
    tic = time.time()
    dilator.reset()
    l.sort()
    dilator.wait()
    dilated_elapsed = time.time() - tic
    print("Dilated speed: {:.1f}ms (actual {:.1f}x, expect {:.1f}x)".format(
        dilated_elapsed*1000, dilated_elapsed / elapsed, dilator._scaling))