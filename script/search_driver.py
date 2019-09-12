import fire
import logging
import logzero
from logzero import logger
import multiprocessing as mp
import random
import time
import yaml

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.filter.bgd_subtract import BackgroundSubtractionFilter
from s3dexp.filter.decoder import DecodeFilter
from s3dexp.filter.facedetector import FaceDetectorFilter
from s3dexp.filter.image_hash import ImageHashFilter
from s3dexp.filter.object_detection import ObjectDetectionFilter
from s3dexp.filter.reader import SimpleReadFilter
from s3dexp.filter.rgbhist import RGBHist1dFilter, RGBHist2dFilter, RGBHist3dFilter
from s3dexp.filter.smart_storage import SmartDecodeFilter
from s3dexp.search import Context, FilterConfig, run_search
from s3dexp.utils import recursive_glob, get_fie_physical_start

logzero.loglevel(logging.INFO)

def run(search_file, base_dir, ext='jpg', num_workers=8, expname_append='', store_result=False, expname=None, sort_fie=False):
    with open(search_file, 'r') as f:
        search_conf = yaml.load(f, Loader=yaml.FullLoader)

    if not expname:
        expname = search_conf['expname']
    expname = expname + expname_append
    logger.info("Using expname: {}".format(expname))

    filter_configs = []
    for el in search_conf['filters']:
        filter_cls = globals()[el['filter']]
        fc = FilterConfig(filter_cls, args=el.get('args', []), kwargs=el.get('kwargs', {}))
        filter_configs.append(fc)

    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))
    if sort_fie:
        paths = sorted(paths, key=get_fie_physical_start)
    else:
        # deterministic pseudo-random
        random.seed(42)
        random.shuffle(paths)

    manager = mp.Manager()
    context = Context(manager)

    tic = time.time()
    run_search(filter_configs, num_workers, paths, context)
    elapsed = time.time() - tic

    logger.info(str(context.stats))

    keys_dict={'expname': expname, 'basedir': base_dir, 'ext': ext, 'num_workers': num_workers, 'hostname': this_hostname}
    vals_dict={
                    'num_items': context.stats['num_items'],
                    'avg_wall_ms': 1e3 * elapsed / context.stats['num_items'],
                    'avg_cpu_ms': 1e3 * context.stats['cpu_time'] / context.stats['num_items'],
                    'avg_mbyteps': context.stats['bytes_from_disk'] * 1e-6 / elapsed,
                }

    logger.info(str(keys_dict))
    logger.info(str(vals_dict))

    if store_result:
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
