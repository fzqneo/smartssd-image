
import cv2
from s3dexp.search import Filter


class RGBHist1dFilter(Filter):
    def __init__(self):
        super(RGBHist1dFilter, self).__init__()

    def __call__(self, item):
        raise NotImplementedError



class RGBHist2dFilter(Filter):
    def __init__(self):
        super(RGBHist2dFilter, self).__init__()

    def __call__(self, item):
        raise NotImplementedError
