import cv2
from google.protobuf.json_format import MessageToJson
import json
from logzero import logger
import os
import time
import zmq

from s3dexp.sim.communication_pb2 import Request, Response
from s3dexp.sim.storage import OP_DECODEONLY, OP_DEBUG_WAIT, OP_DECODE_FACE, OP_DECODE_VIDEO
from s3dexp.utils import recursive_glob

class SmartStorageClient(object):
    """A client talking to an emulated smart storage server. 
    The server is responsible for calculating simulated elapsed time, 
    whereas this client is responsible for generating the actual result faster than simulated speed,
    but blocking-wait for the server's response before returning to the caller.
    The client is not thread-safe.
    """

    def __init__(self, map_from_dir='/mnt/hdd/fast20/jpeg', map_to_ppm_dir='/mnt/ramfs/fast20/ppm', preload=False):
        self.transport = ZMQTransport()
        self.transport.connect()

        assert map_to_ppm_dir is not None and os.path.isdir(map_to_ppm_dir), "Please specific a directory to load PPM"
        assert os.path.isdir(map_from_dir), "Src dir not valid."
        self.map_to_ppm_dir = map_to_ppm_dir
        self.map_from_dir = map_from_dir

        # preload: CAUTION! only used for HD videos. may eat a lot of RAM
        self.preload = preload
        if self.preload:
            logger.warn("Preloading from {}".format(map_to_ppm_dir))
            self.preload_lut = dict()   # ppm_path -> ndarray
            for path in recursive_glob(map_to_ppm_dir, "*.ppm"):
                self.preload_lut[path] = cv2.imread(path, cv2.IMREAD_COLOR)
            logger.warn("Preloaded {} PPM images".format(len(self.preload_lut)))

        # for debugging
        self.late_by = 0.0

    def read_decode(self, path):
        """Perform read for real, and emulate decode"""
        self._read_real(path)
        arr = self.decode_only(path)
        return arr

    def decode_only(self, path):
        # 1. Send the request
        request = Request()
        request.timestamp = time.time()
        request.path = path
        request.opcode = OP_DECODEONLY
        self._send_reqeust(request)

        # 2. Prepare the result
        arr = self._load_decoded(path)

        # 3. Wait for response
        response = self._recv_response()
        return arr

    def read_decode_face(self, path):
        self._read_real(path)
        return self.decode_face(path)

    def decode_face(self, path):
        # 1. Send the request
        request = Request()
        request.timestamp = time.time()
        request.path = path
        request.opcode = OP_DECODE_FACE
        self._send_reqeust(request)

        # 2. Read the ppm
        arr = self._load_decoded(path)

        # 3. Wait for response
        response = self._recv_response()
        boxes = json.loads(response.value)['face_boxes']
        logger.debug("Face: {}, path {}".format(boxes, path))
        return arr, boxes

    def decode_video(self, path, frame_id):
        # 1. Send the request
        request = Request()
        request.timestamp = time.time()
        request.path = path
        request.opcode = OP_DECODE_VIDEO
        request.value = json.dumps({'frame_id': frame_id})
        self._send_reqeust(request)

        # 2. Load PPM
        # hard code mapping scheme for videos
        vid_name = os.path.splitext(os.path.basename(path))[0]
        ppm_path = os.path.join(self.map_to_ppm_dir, vid_name, '%06d.ppm' % (frame_id+1)) # ffmpeg start at 1
        if self.preload:
            arr = self.preload_lut[ppm_path]
        else:
            logger.debug("Try to load PPM from {}".format(ppm_path))
            arr = cv2.imread(ppm_path, cv2.IMREAD_COLOR)

        assert arr is not None, arr

        # 3. Wait for response
        self._recv_response()
        # self._recv()

        return arr

    def debug_wait(self, wait):
        request = Request()
        request.wait = wait
        request.opcode = OP_DEBUG_WAIT
        request.timestamp = time.time()
        self._send_request(request)
        self._recv_response()
        return

    def _send_reqeust(self, pb):
        logger.debug("Sending {}".format(MessageToJson(pb)))
        self.transport.send(pb.SerializeToString())

    def _recv_response(self):
        response = Response()
        body = self.transport.recv()
        response.ParseFromString(body)

        logger.debug("Received {}".format(MessageToJson(response)))

        late = time.time() - response.completion_timestamp
        logger.debug("Simulated elapsed time: {:.3f} ms".format(1000*(response.completion_timestamp - response.request_timestamp)))
        if late > 1e-5:
            logger.debug("Too late by {:.3f} ms".format(late*1000))
        elif late < -1e-5:
            logger.debug("Too early by {:.3f} ms".format(-late*1000))
        self.late_by = self.late_by * .5 + late * .5    # simple running average
        return response

    def _recv(self):
        # recv without parsing and logging. Try to be fast
        return self.transport.recv()

    def _load_decoded(self, path):
        relpath = os.path.relpath(path, self.map_from_dir)
        ppm_path = os.path.splitext(os.path.join(self.map_to_ppm_dir, relpath))[0] + '.ppm'
        arr = cv2.imread(ppm_path, cv2.IMREAD_COLOR)
        return arr

    def _read_real(self, path):
        """Read the file from disk for real so we can actual elapsed time"""
        size = os.path.getsize(path)
        with open(path, 'r') as f:
            fd = f.fileno()
            _ = os.read(fd, size)

    def __del__(self):
        logger.warn("Avg late by {:.3f} ms".format(self.late_by*1000))


class ZMQTransport(object):
    def __init__(self, named_pipe="/tmp/s3dexp-comm"):
        self.named_pipe = named_pipe
        self.subscriber = None
        self.listening = False

    def connect(self):
        if self.listening:
            raise Exception("Client already listening")
        context = zmq.Context()
        self.subscriber = context.socket(zmq.REQ)
        self.subscriber.connect("ipc://" + self.named_pipe)
        self.listening = True

    def close(self):
        if not self.listening:
            raise Exception("Client not listening")
        self.subscriber.close()
        self.listening = False

    def send(self, body):
        self.subscriber.send(body)
        return True

    def recv(self):
        return self.subscriber.recv()
        