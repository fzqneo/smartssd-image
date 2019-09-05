from logzero import logger
import multiprocessing as mp
import numpy as np

class Item(object):
    def __init__(self, src):
        super(Item, self).__init__()
        self._attrs = dict()
        assert isinstance(src, [str, unicode])
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
        assert isinstance(v, np.ndarray)
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
        self._str = "{}({}, {})".format(type(self).__name__, ','.join(args), str(kwargs))
    
    def __call__(self, item):
        raise NotImplementedError

    def __str__(self):
        return self._str


class FilterConfig(object):
    def __init__(self, filter_cls, args=[], kwargs={}):
        super(FilterConfig, self).__init__()
        isinstance(filter_cls, Filter)
        self.filter_cls = filter_cls
        self.args = args
        self.kwargs = kwargs


    def instantiate(self):
        return self.filter_cls(*self.args, **self.kwargs)


def search_work(filter_configs, q, stats):
    assert isinstance(q, mp.JoinableQueue)
    filters = map(filter_configs, lambda fc: fc.instantiate())
    map(map(filter, str), logger.info)

    try:
        while True:
            src = q.get()
            try:
                if src is not None:
                    item = Item(src)
                    for f in filters:
                        f(item)
                    del item
                else:
                    break
            finally:
                q.task_done()
    finally:
        pass

    
def run_search(filter_configs, num_workers, path_list_or_gen):
    # TODO add statistics
    q = mp.JoinableQueue(maxsize=100)
    workers = []
    for i in range(num_workers):
        w = mp.Process(target=search_work, args=(filter_configs, q, None), name='worker-'+i)
        w.daemon = True
        w.start()
        workers.append(w)

    for path in path_list_or_gen:
        q.put(path)

    logger.info("All items pushed. Waiting for search to finish.")
    q.join()
    for w in workers:
        try:
            w.terminate()
        except:
            logger.warn("Fail to terminate {}".format(w.name))