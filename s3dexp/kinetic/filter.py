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

def get_drives_envvar():
    rv = os.getenv('KINETIC_DRIVES').split(' ')
    logger.info("Obtain drives from env var: {}".format(rv))
    return rv

class SimpleKineticGetFilter(Filter):
    def __init__(self, drive_ips=None):
        super(SimpleKineticGetFilter, self).__init__()

        if not drive_ips:
            drive_ips = get_drives_envvar()

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


        # kvclients = []
        # for drive_ip in drive_ips:
        #     kvclient = Client(drive_ip)
        #     kvclient.connect()
        #     assert kvclient.is_connected, "Failed to connect to drive"
        #     logger.info("kv_client connected {}".format(drive_ip))
        #     kvclient.queue_depth = 5
        #     kvclient.callback_delegate = data_callbak
        #     kvclients.append(kvclient)
        # self.kvclients = kvclients
        
        drive_ip = random.choice(drive_ips)        
        kvclient = Client(drive_ip)
        kvclient .connect()
        assert kvclient.is_connected, "Failed to connect to drive"
        logger.info("kv_client connected {}".format(drive_ip))
        kvclient.queue_depth = 5
        kvclient.callback_delegate = data_callbak
        self.kvclient = kvclient


    def __call__(self, item):
        kvclient = self.kvclient
        key = pathlib.Path(item.src).name
        kvclient.get(key)
        kvclient.wait_q(0)
        value = self.result.pop()
        self.session_stats['bytes_from_disk'] += len(value)
        item.data = value
        return True


import numpy as np
from s3dexp.kinetic.proxy_pb2 import Message

class ProxyKineticGetDecodeFilter(Filter):
    def __init__(self, drive_ips=None, base_dir='/home/zf/activedisk/data/flickr15k/', decoded_dir='/mnt/ramfs/', mpixps=140., em_wait=False):
        super(ProxyKineticGetDecodeFilter, self).__init__()

        if not drive_ips:
            drive_ips = get_drives_envvar()

        self.base_dir = pathlib.Path(base_dir).resolve()
        self.decoded_dir = pathlib.Path(decoded_dir).resolve()
        self.mpixps = mpixps
        self.em_wait = em_wait

        # pxclients = []
        # for drive_ip in drive_ips:
        #     pxclient = KineticProxyClient(drive_ip)
        #     pxclient.connect()
        #     pxclients.append(pxclient)
        # self.pxclients = pxclients

        drive_ip = random.choice(drive_ips)
        pxclient = KineticProxyClient(drive_ip)
        pxclient.connect()
        self.pxclient = pxclient


    def __call__(self, item):
        # load ppm and emulate decode time
        tic = time.time()
        abspath = pathlib.Path(item.src).resolve()

        # .npy files are somewhat faster than .ppm
        npy_path = (self.decoded_dir / abspath.relative_to(self.base_dir.parent)).with_suffix('.npy')
        arr = np.load(npy_path)
        logger.debug("Loading decoded file from {}".format(npy_path))


        item.array = arr
        simulated_deocde_time = arr.shape[0] * arr.shape[1] / 1e6 / self.mpixps

        if self.em_wait:
            sleep = simulated_deocde_time - (time.time() - tic)
            if sleep > 1e-3:
                time.sleep(.9 * sleep)
            elif sleep < -1e-3:
                # logger.warn("Too late to emulate decode: {:.4f}, {}, {}x{}".format(sleep, ppm_path, arr.shape[0], arr.shape[1]))
                pass

        # issue get_smart with emulated decode to proxy
        pxclient = self.pxclient
        key = abspath.name
        
        # hack for speed: send request and get reply separately. Don't parse reply
        req_msg = pxclient.request_msg
        # req_msg.Clear()   # Clear() takes about 1ms. WTH
        req_msg.opcode = Message.Opcode.GETSMART
        req_msg.key = key
        req_msg.size = arr.size
        pxclient._send_request_msg()
        _ = pxclient._recv()    # recv w/o parsing
        
        self.session_stats['bytes_from_disk'] += arr.size
        return True

