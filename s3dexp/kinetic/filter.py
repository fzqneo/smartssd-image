from __future__ import absolute_import, division, print_function

import os
import random
import time

import cv2
from logzero import logger
import pathlib2 as pathlib

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

from s3dexp.search import Filter
from s3dexp.kinetic.proxy_client import KineticProxyClient



class SimpleKineticGetFilter(Filter):
    def __init__(self, drive_ips):
        super(SimpleKineticGetFilter, self).__init__()

        self.result = []
        def data_callbak(msg, cmd, value):
            key = bytes(cmd.body.keyValue.key)
            if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
                logger.error("\t Key: " +  str(cmd.body.keyValue.key) + \
                            ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
                            ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                            ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
                value = b''
            else:
                logger.debug("[get] Success: GET " + str(cmd.body.keyValue.key))
                value = value

            self.result.append(bytes(value))


        kvclients = []
        for drive_ip in drive_ips:
            kvclient = Client(drive_ip)
            kvclient .connect()
            assert kvclient.is_connected, "Failed to connect to drive"
            logger.info("kv_client connected {}".format(drive_ip))
            kvclient.queue_depth = 5
            kvclient.callback_delegate = data_callbak
            kvclients.append(kvclient)

        self.kvclients = kvclients

    def __call__(self, item):
        kvclient = random.choice(self.kvclients)
        key = pathlib.Path(item.src).name
        kvclient.get(key)
        kvclient.wait_q(0)
        value = self.result.pop()
        self.session_stats['bytes_from_disk'] += len(value)
        item.data = value
        return True


# class ProxyKineticGetFilter(Filter):
#     def __init__(self, drive_ip):
#         super(ProxyKineticGetFilter, self).__init__()
#         pxclient = KineticProxyClient(drive_ip)
#         pxclient.connect()
#         # logger.info("Connected to Kinetic proxy at {}".format(drive_ip))
#         self.pxclient = pxclient

#     def __call__(self, item):
#         key = pathlib.Path(item.src).name
#         value = self.pxclient.get(key)
#         self.session_stats['bytes_from_disk'] += len(value)
#         item.data = value
#         return True


class ProxyKineticGetDecodeFilter(Filter):
    def __init__(self, drive_ips, base_dir='/home/zf/activedisk/data/flickr15k/', ppm_dir='/mnt/ramfs/ppm/', mpixps=140., em_wait=False):
        super(ProxyKineticGetDecodeFilter, self).__init__()
        self.base_dir = pathlib.Path(base_dir).resolve()
        self.ppm_dir = pathlib.Path(ppm_dir).resolve()
        self.mpixps = mpixps
        self.em_wait = em_wait

        pxclients = []
        for drive_ip in drive_ips:
            pxclient = KineticProxyClient(drive_ip)
            pxclient.connect()
            pxclients.append(pxclient)
        self.pxclients = pxclients


    def __call__(self, item):
        # load ppm and emulate decode time
        tic = time.time()
        abspath = pathlib.Path(item.src).resolve()
        ppm_path = (self.ppm_dir / abspath.relative_to(self.base_dir.parent)).with_suffix('.ppm') # include the dataset name
        logger.debug("Loading PPM from {}".format(ppm_path))
        arr = cv2.imread(str(ppm_path), cv2.IMREAD_COLOR)
        item.array = arr
        simulated_deocde_time = arr.shape[0] * arr.shape[1] / 1e6 / self.mpixps

        if self.em_wait:
            sleep = simulated_deocde_time - (time.time() - tic)
            if sleep > 0:
                time.sleep(.9 * sleep)
            elif sleep < -1e-3:
                logger.warn("Too late to emulate decode: {:.4f}, {}, {}x{}".format(sleep, ppm_path, arr.shape[0], arr.shape[1]))

        # issue get_smart with emulated decode to proxy
        pxclient = random.choice(self.pxclients)
        key = abspath.name
        _ = pxclient.get_smart(key, arr.size)
        self.session_stats['bytes_from_disk'] += arr.size
        return True
