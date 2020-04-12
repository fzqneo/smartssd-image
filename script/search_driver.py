from __future__ import absolute_import, division, print_function

import json
import logging
import multiprocessing as mp
import random
import time

import fire
import logzero
from logzero import logger
import pathlib
import psutil
import yaml

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.filter.bgd_subtract import BackgroundSubtractionFilter
from s3dexp.filter.classification import ClassificationFilter
from s3dexp.filter.color import ColorFilter
from s3dexp.filter.decoder import DecodeFilter
from s3dexp.filter.facedetector import FaceDetectorFilter, ObamaDetectorFilter
from s3dexp.filter.image_hash import ImageHashFilter
from s3dexp.filter.object_detection import ObjectDetectionFilter
from s3dexp.filter.reader import SimpleReadFilter
from s3dexp.filter.rgbhist import RGBHist1dFilter, RGBHist2dFilter, RGBHist3dFilter
from s3dexp.filter.smart_storage import SmartDecodeFilter, SmartFaceFilter
from s3dexp.kinetic.getter import *
from s3dexp.search import Context, FilterConfig, run_search
from s3dexp.utils import recursive_glob, get_fie_physical_start

logzero.loglevel(logging.INFO)

CPU_START = (0, 6)    # pin on NUMA node 0

def run(
    search_file, base_dir, ext='.jpg', num_workers=8, 
    store_result=False, expname=None, sort=None, 
    verbose=False):
    """Run a search consisting of a filter chain defined in an input 'search file'
    
    Arguments:
        search_file {str} -- path to a yml file
        base_dir {str} -- diretory to glob files to process
    
    Keyword Arguments:
        ext {str} -- file extension filter (default: {'jpg'})
        num_workers {int} -- number of parallel workers (default: {8})
        store_result {bool} -- whether store measurements to DB (default: {False})
        expname {[type]} -- expname in DB. If not provided, will try to use from search_file (default: {None})
        sort {str or None} -- sort the paths by 'fie' (Linux FIE), 'name' (file name), or None (random)
        verbose {bool} -- [description] (default: {False})
    """

    if verbose:
        logzero.loglevel(logging.DEBUG)

    with open(search_file, 'r') as f:
        search_conf = yaml.load(f, Loader=yaml.FullLoader)

    # prepare CPU affinity
    assert num_workers ==1 or num_workers % 2 == 0, "Must give an even number for num_workers or 1: {}".format(num_workers)
    if num_workers > 1:
        cpuset = range(CPU_START[0], int(CPU_START[0] + num_workers /2)) + range(CPU_START[1], int(CPU_START[1] + num_workers / 2))
    else:
        cpuset = [CPU_START[0], ]
    logger.info("cpuset: {}".format(cpuset))
    psutil.Process().cpu_affinity(cpuset)

    # prepare expname
    if not expname:
        expname = search_conf['expname']
        logger.warn("No expname given on cmd. Use from {}: {}".format(search_file, expname))
    logger.info("Using expname: {}".format(expname))

    # prepare filter configs
    filter_configs = []
    for el in search_conf['filters']:
        filter_cls = globals()[el['filter']]
        fc = FilterConfig(filter_cls, args=el.get('args', []), kwargs=el.get('kwargs', {}))
        filter_configs.append(fc)

    # prepare and sort paths
    assert sort in (None, 'fie', 'name')
    base_dir = str(pathlib.Path(base_dir).resolve())
    paths = list(filter(lambda p: p.suffix == ext, pathlib.Path(base_dir).rglob('*')))
    paths = list(map(str, paths))
    if sort == 'fie':
        logger.info("Sort paths by FIE")
        paths = sorted(paths, key=get_fie_physical_start)
    elif sort == 'name':
        logger.info("Sort paths by name")
        paths = sorted(paths, key=lambda p: pathlib.Path(p).name)
    else:
        # deterministic pseudo-random
        random.seed(42)
        random.shuffle(paths)
    logger.info("Find {} files under {}".format(len(paths), base_dir))

    # create shared data structure by workers
    manager = mp.Manager()
    context = Context(manager)

    # run the search with parallel workers
    tic = time.time()
    run_search(filter_configs, num_workers, paths, context)
    elapsed = time.time() - tic

    logger.info("End-to-end elapsed time {:.3f} s".format(elapsed))
    logger.info(str(context.stats))

    keys_dict={'expname': expname, 'basedir': base_dir, 'ext': ext, 'num_workers': num_workers, 'hostname': this_hostname}
    vals_dict={
                    'num_items': context.stats['num_items'],
                    'avg_wall_ms': 1e3 * elapsed / context.stats['num_items'],
                    'avg_cpu_ms': 1e3 * context.stats['cpu_time'] / context.stats['num_items'],
                    'avg_mbyteps': context.stats['bytes_from_disk'] * 1e-6 / elapsed,
                }

    logger.info(json.dumps(keys_dict))
    logger.info(json.dumps(vals_dict))
    logger.info("obj tput: {}".format(1000 // vals_dict['avg_wall_ms']))

    if store_result:
        logger.warn("Writing result to DB expname={}".format(expname))
        sess = dbutils.get_session()
        dbutils.insert_or_update_one(
            sess, 
            dbmodles.EurekaExp,
            keys_dict=keys_dict,
            vals_dict=vals_dict)
        sess.commit()
        sess.close()


if __name__ == '__main__':
    fire.Fire(run)
