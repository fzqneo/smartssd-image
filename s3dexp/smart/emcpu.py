from logzero import logger
import time

class ProcessDilator(object):
    """Simulate the in-process computation time between reset() and dilate()
    if it were run on a slower processor.
    """
    
    def __init__(self, target_ghz, target_n_cores=1, platform_ghz=3.0):
        super(ProcessDilator, self).__init__()
        assert 0 < target_ghz < platform_ghz
        assert isinstance(target_n_cores, int)
        self._scaling = platform_ghz / float(target_ghz)
        logger.info("Dilator scale factor: {}".format(self._scaling))
        self._tic = time.clock()
        self.target_n_cores = target_n_cores

    def reset(self):
        self._tic = time.clock()

    def dilate(self):
        """Return the simulated elapsed CPU
        
        Returns:
            float -- Simulated elapsed CPU time if computation between
            reset() and dilate() were run on the simulated CPU.
        """
        elapsed_cputime = time.clock() - self._tic
        return elapsed_cputime * self._scaling / self.target_n_cores


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
    sim_elapsed= dilator.dilate()
    print("Dilated speed: {:.1f}ms (actual {:.1f}x, expect {:.1f}x)".format(
        sim_elapsed*1000, sim_elapsed / elapsed, dilator._scaling))