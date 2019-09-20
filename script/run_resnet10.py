import cv2
import fire
import logging
import logzero
from logzero import logger
import math
import multiprocessing as mp
import numpy as np
import os
from PIL import Image
import psutil
import random
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from torch.autograd import Variable
import torchvision

from s3dexp import this_hostname
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.search import Context
from s3dexp.sim.client import SmartStorageClient
from s3dexp.utils import recursive_glob, get_fie_physical_start

RESOL = (65, 65)

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


class ImageDataset(torch.utils.data.Dataset):
    def __init__(self, files, context, transform=None, smart=False):
        self.files = files
        self.transform = transform
        self.smart = smart
        self.context = context
        self.ss_client = None

        # Acccording to https://pytorch.org/docs/stable/data.html#multi-process-data-loading
        # This data structure will be passed to multiprocessing if num_workers > 0.
        # So we defer creation of client after the process is created,
        # otherwise ZMQ doesn't work properly

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        tic_cpu = time.clock()

        if torch.is_tensor(idx):
            idx = idx.tolist()

        logger.debug("[{}] getitem {}".format(os.getpid(), idx))

        if self.smart:
            # idx is ignored. Pop a path from the (pre-sorted) queue
            img_path = self.context.q.get()
        else:
            img_path = self.files[idx]

        # initialize smart client on the first use
        if self.smart and self.ss_client is None:
            logger.info("[Worker {}] Creating a SmartStorageClient".format(torch.utils.data.get_worker_info().id))
            self.ss_client = SmartStorageClient()

        # get decoded Image
        if self.smart:
            tic = time.time()
            arr = self.ss_client.read_decode(img_path)
            image = cv2.resize(arr, RESOL)    # resize here rather than transform

            disk_read = arr.size
            elapsed = time.time() - tic
            logger.debug("Smart decode {:.3f} ms".format(1000*elapsed))
        else:
            image = default_loader(img_path)
            disk_read = os.path.getsize(img_path)

        # transform
        if self.transform:
            tic = time.time()
            image_tensor = self.transform(image)
            elapsed = time.time() - tic
            logger.debug("Transform {:.3f} ms".format(1000*elapsed))

        # high overhead locking
        with self.context.lock:
            self.context.stats['cpu_time'] += time.clock() - tic_cpu
            self.context.stats['bytes_from_disk'] += disk_read

        return image_tensor

    def __del__(self):
        logger.info("Destroying ImageDataset Worker")

# From:
# https://github.com/pytorch/vision/blob/master/torchvision/datasets/folder.py#L153
def pil_loader(path):
    # open path as file to avoid ResourceWarning (https://github.com/python-pillow/Pillow/issues/835)
    with open(path, 'rb') as f:

        # start = time.time()
        img = Image.open(f)
        img = img.convert('RGB')
        # end = time.time()
        # print('PIL Jpeg time', end - start)
        return img


def accimage_loader(path):
    import accimage
    try:
        start = time.time()
        img = accimage.Image(path)
        end = time.time()
        logger.debug('accimage decode {:.3f} ms'.format(1000*(end - start)))

        return img
    except IOError:
        # Potentially a decoding problem, fall back to PIL.Image
        return pil_loader(path)


def default_loader(path):
    from torchvision import get_image_backend
    if get_image_backend() == 'accimage':
        return accimage_loader(path)
    else:
        return pil_loader(path)


logzero.loglevel(logging.INFO)
CPU_START = (18, 54)    # pin on NUMA node 1

def main(
    base_dir='/mnt/hdd/fast20/jpeg/flickr2500', ext='jpg', 
    num_workers=4, sort_fie=False, smart=False, batch_size=64,
    verbose=False, use_accimage=True, expname=None):
    
    if verbose:
        logzero.loglevel(logging.DEBUG)

    # prepare CPU affinity
    assert num_workers ==1 or num_workers % 2 == 0, "Must give an even number for num_workers or 1: {}".format(num_workers)
    if num_workers > 1:
        cpuset = range(CPU_START[0], CPU_START[0] + num_workers /2) + range(CPU_START[1], CPU_START[1] + num_workers / 2)
    else:
        cpuset = [CPU_START[0], ]
    logger.info("cpuset: {}".format(cpuset))
    psutil.Process().cpu_affinity(cpuset)

    # prepare paths
    paths = list(recursive_glob(base_dir, '*.{}'.format(ext)))
    if sort_fie:
        paths = sorted(paths, key=get_fie_physical_start)
    else:
        # deterministic pseudo-random
        random.seed(42)
        random.shuffle(paths)

    if use_accimage:
        torchvision.set_image_backend('accimage')

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

    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                             std=[0.229, 0.224, 0.225])

    # prepare preprocessing pipeline
    if smart:
        # do resizing using OpenCV in ImageDataSet
        # because ndarray -> PIL conversion is an overhead
        preprocess = transforms.Compose([
            transforms.ToTensor(),
            normalize
        ])
    else:
        preprocess = transforms.Compose([
            transforms.Resize(RESOL),
            transforms.ToTensor(),
            normalize
        ])

    manager = mp.Manager()
    context = Context(manager, qsize=len(paths)+1)

    # hack for smart batch: enque all paths in the beginning to force sequential access
    map(context.q.put, paths)

    image_dataset = ImageDataset(paths, context, transform=preprocess, smart=smart)
    loader = torch.utils.data.DataLoader(
        image_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers,
        pin_memory=True)

    logger.info("warm up with a fake batch")
    fake_batch = torch.zeros([batch_size, 3] + list(RESOL), dtype=torch.float32)
    fake_batch = fake_batch.cuda()
    print fake_batch.shape, fake_batch.dtype
    _ = model(fake_batch)

    tic = time.time()
    tic_cpu = time.clock()
    num_batches = 0

    for image_tensor in loader:

        image_tensor = image_tensor.cuda()
        # print image_tensor.shape, image_tensor.dtype

        batch_tic = time.time()
        output = model(image_tensor)

        logger.info("Run batch {} in {:.3f} ms".format(num_batches, 1000*(time.time()-batch_tic)))
        num_batches += 1

    elapsed = time.time() - tic
    elapsed_cpu = time.clock() - tic_cpu
    elapsed_cpu += context.stats['cpu_time']    # TODO add CPU time of workers

    logger.info("# batches: {}".format(num_batches))

    num_items = len(paths)
    logger.info("Elapsed {:.3f} ms, CPU elapsed {:.3f} ms / image".format(1000*elapsed/num_items, 1000*elapsed_cpu/num_items))
    logger.info(str(context.stats))

    keys_dict={'expname': expname, 'basedir': base_dir, 'ext': ext, 'num_workers': num_workers, 'hostname': this_hostname}
    vals_dict={
                    'num_items': num_items,
                    'avg_wall_ms': 1e3 * elapsed / num_items,
                    'avg_cpu_ms': 1e3 * elapsed_cpu / num_items,
                    'avg_mbyteps': context.stats['bytes_from_disk'] * 1e-6 / elapsed,
                }

    logger.info(str(keys_dict))
    logger.info(str(vals_dict))

    if expname:
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
