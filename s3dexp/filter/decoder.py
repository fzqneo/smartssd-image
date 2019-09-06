import cv2
import numpy as np
from io import BytesIO
from logzero import logger
from s3dexp.search import Filter
import traceback


class DecodeFilter(Filter):
    def __init__(self):
        super(DecodeFilter, self).__init__()

    def __call__(self, item):
        bgr = cv2.imdecode(np.frombuffer(item.data, np.int8), cv2.IMREAD_COLOR)
        item.array = bgr
        return True
