
import fire
import logging
import logzero
from logzero import logger
import multiprocessing as mp
import random
from s3dexp.filter.decoder import DecodeFilter
from s3dexp.filter.reader import SimpleReadFilter
from s3dexp.filter.rgbhist import RGBHist1dFilter, RGBHist2dFilter
from s3dexp.search import Context, FilterConfig, run_search
from s3dexp.utils import recursive_glob
import time
import yaml

logzero.loglevel(logging.INFO)

def run(search_file, base_dir, ext='jpg', num_workers=36, expname_append=''):
    with open(search_file, 'r') as f:
        search_conf = yaml.load(f)

    expname = search_conf['expname']
    expname += expname_append
    logger.info("Using expname: {}".format(expname))

    filter_configs = []
    for el in search_conf['filters']:
        filter_cls = globals()[el['filter']]
        fc = FilterConfig(filter_cls, args=el.get('args', []), kwargs=el.get('kwargs', {}))
        filter_configs.append(fc)

    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))
    # deterministic pseudo-random
    random.seed(42)
    random.shuffle(paths)

    manager = mp.Manager()
    context = Context(manager)

    tic = time.time()
    run_search(filter_configs, num_workers, paths, context)
    elapsed = time.time() - tic

    print context.stats


if __name__ == '__main__':
    fire.Fire(run)