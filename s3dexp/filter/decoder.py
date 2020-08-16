import io
import pathlib
import traceback

import cv2
import numpy as np
from logzero import logger

from s3dexp.search import Filter


class DecodeFilter(Filter):
    def __init__(self):
        super(DecodeFilter, self).__init__()

    def __call__(self, item):
        if  pathlib.Path(item.src).suffix == '.npy':
            item.array = np.load(io.BytesIO(item.data))
        else:
            bgr = cv2.imdecode(np.frombuffer(item.data, np.int8), cv2.IMREAD_COLOR)
            item.array = bgr
        return True
