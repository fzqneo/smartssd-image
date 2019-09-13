import collections
from logzero import logger
import multiprocessing as mp
import numpy as np
import time
import os

class Item(object):
    def __init__(self, src):
        super(Item, self).__init__()
        self._attrs = dict()
        assert isinstance(src, (str, unicode))
        self._attrs['_src'] = src

    @property
    def src(self):
        return self._attrs['_src']

    @property
    def data(self):
        return self._attrs['']

    @data.setter
    def data(self, v):
        self._attrs[''] = v

    @property
    def array(self):
        return self._attrs['_array']

    @array.setter 
    def array(self, v):
        assert isinstance(v, np.ndarray), "Expect numpy array, got {}".format(type(v))
        self._attrs['_array'] = v

    def __getitem__(self, key):
        return self._attrs[key]

    def __setitem__(self, key, val):
        self._attrs[key] = val

    def __contains__(self, key):
        return key in self._attrs


class Filter(object):
    def __init__(self, *args, **kwargs):
        super(Filter, self).__init__()
        self._str = "{}({}, {})".format(type(self).__name__, ','.join(map(str,args)), str(kwargs))
    
    def __call__(self, item):
        raise NotImplementedError

    def __str__(self):
        return self._str

    def set_session_stats(self, dct):
        # Pass in an external dict for logging session-wide statistics,
        # e.g., bytes read from (emulated) disk
        self.session_stats = dct


class FilterConfig(object):
    def __init__(self, filter_cls, args=[], kwargs={}):
        super(FilterConfig, self).__init__()
        isinstance(filter_cls, Filter)
        self.filter_cls = filter_cls
        self.args = args
        self.kwargs = kwargs

    def instantiate(self):
        return self.filter_cls(*self.args, **self.kwargs)


class Context(object):
    """Shared data structure by multi processes. Don't update it too frequently."""
    def __init__(self, manager):
        super(Context, self).__init__()
        self.lock = manager.Lock()
        self.q = manager.JoinableQueue(1000)
        self.stats = manager.dict(
            num_items=0,
            num_workers=0,
            cpu_time=0.,
            passed_items=0,
            bytes_from_disk=0,
        )


def search_work(filter_configs, context):
    assert isinstance(context, Context)
    logger.info("[Worker {}] started".format(os.getpid()))
    filters = map(lambda fc: fc.instantiate(), filter_configs)
    map(logger.info, map(str, filters))

    tic_cpu = time.clock()
    count = 0
    count_passed = 0

    session_stats = collections.defaultdict(float)
    for f in filters:
        f.set_session_stats(session_stats)

    try:
        while True:
            src = context.q.get()
            try:
                if src is not None:
                    item = Item(src)
                    passed = True
                    for f in filters:
                        ret = f(item)
                        passed = passed and ret
                        if not passed:
                            break
                    del item
                    count += 1
                    count_passed += int(passed)
                    if passed:
                        logger.debug("Accepted {}".format(src))
                else:
                    logger.info("[Worker {}] terminating on receiving None ".format(os.getpid()))
                    break
            except Exception as e:
                logger.error("Exception on {}".format(src))
                logger.exception(e)
            finally:
                context.q.task_done()
    finally:
        elapsed_cpu = time.clock() - tic_cpu
        logger.info("[Worker {}] num_items {}, passed_items {}, elapsed_cpu: {}, session_stats: {}".format(
            os.getpid(), count, count_passed, elapsed_cpu, str(session_stats)))
        with context.lock:
            context.stats['num_workers'] += 1
            context.stats['num_items'] += count
            context.stats['cpu_time'] += elapsed_cpu
            context.stats['passed_items'] += count_passed
            context.stats['bytes_from_disk'] += session_stats['bytes_from_disk']

    
def run_search(filter_configs, num_workers, path_list_or_gen, context):
    workers = []
    for i in range(num_workers):
        w = mp.Process(target=search_work, args=(filter_configs, context), name='worker-{}'.format(i))
        w.daemon = True
        w.start()
        workers.append(w)

    for i, path in enumerate(path_list_or_gen):
        if i % 1000 == 0:
            logger.info("Enque'd {} items".format(i))
        logger.debug("Enque'ing {}".format(path))
        context.q.put(path)
    # push None as sentinel
    for _ in workers:
        context.q.put(None)

    logger.info("All items pushed. Waiting for search to finish.")
    context.q.join()

    for w in workers:
        try:
            w.join(5)
        except:
            logger.warn("Fail to terminate {}".format(w.name))