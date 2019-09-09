import itertools
import cv2
import numpy
from s3dexp.search import Filter

class RGBHist1dFilter(Filter):
    def __init__(self):
        super(RGBHist1dFilter, self).__init__()

    def __call__(self, item):
        hists = []
        num_channels = len(item.array.shape)
        for i in range(num_channels):  # channels
            hist = cv2.calcHist([item.array, ], [i, ], None, [256, ], [0, 256])
            hists.append(hist)
        item['rgb_hist_1d'] = hists
        return True


class RGBHist2dFilter(Filter):
    def __init__(self):
        super(RGBHist2dFilter, self).__init__()

    def __call__(self, item):
        num_channels = len(item.array.shape)
        if num_channels == 3:
            hists = []
            clr_iter = [i for i in itertools.combinations(range(num_channels),2)]
            for (a, b) in clr_iter:
                hist = cv2.calcHist([item.array,], [a, b], None, [32, 32], [0, 256, 0, 256])
                hists.append(hist)
        else:
            hists = cv2.calcHist([item.array,], [0], None, [256, ], [0, 256])
        item['rgb_hist_2d'] = hists
        return True

