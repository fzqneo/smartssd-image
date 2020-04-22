# import cv2
import fire
import itertools
import logging
import logzero
from logzero import logger
import math
import multiprocessing as mp
import numpy as np
import os
import pathlib2 as pathlib
from PIL import Image
import psutil
import random
import threading
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from torch.autograd import Variable
import torchvision
from tqdm import tqdm

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.filter.decoder import DecodeFilter
from s3dexp.filter.reader import SimpleReadFilter
from s3dexp.filter.smart_storage import *
from s3dexp.kinetic.filter import *
from s3dexp.search import Context, Filter, FilterConfig, run_search
from s3dexp.sim.client import SmartStorageClient
from s3dexp.utils import recursive_glob, get_fie_physical_start

RESOL = (65, 65)


# https://github.com/SeanNaren/deepspeech.pytorch/issues/270#issuecomment-377672447

class MyModuleList(nn.ModuleList):
    def __add__(self, x):
        tmp = [m for m in self.modules()] + [m for m in x.modules()]
        return MyModuleList(tmp)
    def forward(self, x):
        for layer in self:
            x = layer(x)
        return x

def make_basic_block(inplanes, planes, stride=1, downsample=None):
    def conv3x3(in_planes, out_planes, stride=1):
        return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                         padding=1, bias=False)

    block_list = MyModuleList([
            conv3x3(inplanes, planes, stride),
            nn.BatchNorm2d(planes),
            nn.ReLU(inplace=True),
            conv3x3(planes, planes),
            nn.BatchNorm2d(planes),
    ])
    if downsample == None:
        residual = MyModuleList([])
    else:
        residual = downsample
    return MyModuleList([block_list, residual])

def make_bottleneck_block(inplanes, planes, stride=1, downsample=None):
    block_list = MyModuleList([
            # conv bn relu
            nn.Conv2d(inplanes, planes, kernel_size=1, bias=False),
            nn.BatchNorm2d(planes),
            nn.ReLU(inplace=True),
            # conv bn relu
            nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                      padding=1, bias=False),
            nn.BatchNorm2d(planes),
            nn.ReLU(inplace=True),
            # conv bn
            nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False),
            nn.BatchNorm2d(planes * 4),
    ])
    if downsample == None:
        residual = MyModuleList([])
    else:
        residual = downsample
    return (block_list, residual)

class PytorchResNet(nn.Module):
    def __init__(self, section_reps,
                 num_classes=1000, nbf=64,
                 conv1_size=7, conv1_pad=3,
                 downsample_start=True,
                 use_basic_block=True):
        super(PytorchResNet, self).__init__()

        if use_basic_block:
            self.expansion = 1
            self.block_fn = make_basic_block
        else:
            self.expansion = 4
            self.block_fn = make_bottleneck_block
        self.downsample_start = downsample_start
        self.inplanes = nbf

        self.conv1 = nn.Conv2d(3, nbf, kernel_size=conv1_size,
                               stride=downsample_start + 1, padding=conv1_pad, bias=False)
        self.bn1 = nn.BatchNorm2d(nbf)

        sections = []
        for i, section_rep in enumerate(section_reps):
            sec = self._make_section(nbf * (2 ** i), section_rep, stride=(i != 0) + 1)
            sections.append(sec)
        self.sections = MyModuleList(sections)
        lin_inp = nbf * int(2 ** (len(section_reps) - 1)) * self.expansion \
            if len(self.sections) != 0 else nbf
        self.fc = nn.Linear(lin_inp, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_section(self, planes, num_blocks, stride=1):
        if stride != 1 or self.inplanes != planes * self.expansion:
            downsample = MyModuleList([
                    nn.Conv2d(self.inplanes, planes * self.expansion,
                              kernel_size=1, stride=stride, bias=False),
                    nn.BatchNorm2d(planes * self.expansion),
            ])
        else:
            downsample = None

        blocks = []
        blocks.append(self.block_fn(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * self.expansion
        for i in range(1, num_blocks):
            blocks.append(self.block_fn(self.inplanes, planes))

        return MyModuleList(blocks)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = F.relu(x)
        if self.downsample_start:
            x = F.max_pool2d(x, kernel_size=3, stride=2, padding=1)

        for sec_ind, section in enumerate(self.sections):
            for block_ind, (block, shortcut) in enumerate(section):
                x_input = x
                if len(shortcut) != 0:
                    x = shortcut(x)
                x_conv = block(x_input)
                x = x + x_conv
                x = F.relu(x)

        x = F.avg_pool2d(x, (x.size(2), x.size(3)))
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x


class TransformAndSendFilter(Filter):

    def __init__(self, transform_fn, out_q, resize_to=RESOL):
        super(TransformAndSendFilter, self).__init__(transform_fn, out_q)
        self.transform_fn = transform_fn
        self.out_q = out_q
        self.resize_to = resize_to

    def __call__(self, item):
        import cv2
        if self.resize_to:
            arr = cv2.resize(item.array, self.resize_to)
        else:
            arr = item.array
        rv = self.transform_fn(arr)
        self.out_q.put(rv)
        return True


logzero.loglevel(logging.INFO)
CPU_START = (0, 36)    # pin on NUMA node 1

def main(
    base_dir='/home/zf/activedisk/data/flickr15k/', ext='.jpg', sort=None, 
    num_cores=8, workers_per_core=1,
    smartsim=False, kinetic=False, kproxy=False,
    batch_size=64,
    store_result=False, expname=None, verbose=False, ):

    if verbose:
        logzero.loglevel(logging.DEBUG)

    # prepare CPU affinity
    assert num_cores ==1 or num_cores % 2 == 0, "Must give an even number for num_cores or 1: {}".format(num_cores)
    if num_cores > 1:
        cpuset = range(CPU_START[0], int(CPU_START[0] + num_cores /2)) + range(CPU_START[1], int(CPU_START[1] + num_cores / 2))
    else:
        cpuset = [CPU_START[0], ]
    logger.info("cpuset: {}".format(cpuset))
    psutil.Process().cpu_affinity(cpuset)

    # prepare expname
    assert not store_result or expname is not None
    logger.info("Using expname: {}".format(expname))

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
        logger.info("Shuffle paths")
        random.seed(42)
        random.shuffle(paths)
    logger.info("Find {} files under {}".format(len(paths), base_dir))


    trn_name = 'trn10'  # taipei-scrubbing.py in Blazeit
    # trn_name = 'trn18'  # end2end.py in Blazeit
    trn_name_to_layers = \
        [('trn10', [1, 1, 1, 1]),
         ('trn18', [2, 2, 2, 2]),
         ('trn34', [3, 4, 6, 3])]
    trn_name_to_layers = dict(trn_name_to_layers)

    model = PytorchResNet(
                trn_name_to_layers[trn_name], num_classes=2,
                conv1_size=3, conv1_pad=1, nbf=16, downsample_start=False)
    model.cuda()


    # prepare the transform pipeline
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                             std=[0.229, 0.224, 0.225])

    # all options use cv2 for decoding and resizing
    # transform: ndarray -> Tensor
    preprocess = transforms.Compose([
        transforms.ToTensor(),
        normalize
    ])

    # Queue to collect decoded and preprocessed samples
    preprocessed_q = mp.Queue()

    # prepare the filter chain
    if smartsim:
        logger.warn("Using sim smart storage decoder")
        filter_configs = [
            FilterConfig(SmartDecodeFilter),
        ]
    elif kinetic:
        logger.warn("Using kinetic client + naive decode")
        filter_configs = [
            FilterConfig(SimpleKineticGetFilter),
            FilterConfig(DecodeFilter),
        ]
    elif kproxy:
        logger.warn("Using kproxy with on-drive decode")
        filter_config = [
            FilterConfig(ProxyKineticGetDecodeFilter),
        ]
    else:
        filter_configs = [
            FilterConfig(SimpleReadFilter),
            FilterConfig(DecodeFilter),
        ]

    filter_configs.append(FilterConfig(TransformAndSendFilter, args=(preprocess, preprocessed_q)))

    manager = mp.Manager()
    context = Context(manager)

    logger.info("warm up DNN with a fake batch")
    fake_batch = torch.zeros([batch_size, 3] + list(RESOL), dtype=torch.float32)
    fake_batch = fake_batch.cuda()
    print fake_batch.shape, fake_batch.dtype
    _ = model(fake_batch)

    tic = time.time()
    tic_cpu = time.clock()
    num_batches = 0
    last_batch_time = tic
    elapsed_gpu = 0.

    search_thread = threading.Thread(target=run_search, args=(filter_configs, num_cores*workers_per_core, paths, context))
    search_thread.daemon = True
    search_thread.start()

    for batch_id in tqdm(range(int(len(paths)/batch_size))):
        image_tensor = torch.stack([preprocessed_q.get() for _ in range(batch_size)])
        image_tensor = image_tensor.cuda()
        # print image_tensor.shape, image_tensor.dtype

        tic_gpu = time.time()
        output = model(image_tensor)
        now = time.time()

        logger.debug("Run batch {} in {:.3f} ms".format(num_batches, 1000*(now-last_batch_time)))
        logger.debug("Batch GPU time: {:.3f} ms".format(1000*(now-tic_gpu)))

        last_batch_time = now
        elapsed_gpu += (now - tic_gpu)
        num_batches += 1

    # flush the last batch
    for _ in range(len(paths) - num_batches * batch_size):
        preprocessed_q.get()

    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu

    search_thread.join()

    elapsed_cpu += context.stats['cpu_time']   
    num_items = num_batches * batch_size
    bytes_from_disk = context.stats['bytes_from_disk']

    logger.info("# batches: {}".format(num_batches))
    logger.info("GPU time per batch {:.3f} ms, GPU time per image {:.3f} ms".format(1000*elapsed_gpu/num_batches, 1000*elapsed_gpu/num_batches/batch_size))

    logger.info("Elapsed {:.3f} ms, CPU elapsed {:.3f} ms / image".format(1000*elapsed/num_items, 1000*elapsed_cpu/num_items))
    logger.info(str(context.stats))

    keys_dict={'expname': expname, 'basedir': base_dir, 'ext': ext, 'num_workers': num_cores, 'hostname': this_hostname}
    vals_dict={
                    'num_items': num_items,
                    'avg_wall_ms': 1e3 * elapsed / num_items,
                    'avg_cpu_ms': 1e3 * elapsed_cpu / num_items,
                    'avg_mbyteps': bytes_from_disk * 1e-6 / elapsed,
                }

    logger.info(str(keys_dict))
    logger.info(str(vals_dict))
    logger.info("obj tput: {}".format(1000 // vals_dict['avg_wall_ms']))

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
    fire.Fire(main)
