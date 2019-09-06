
import cv2
import numpy
from s3dexp.search import Filter


class RGBHist1dFilter(Filter):
    def __init__(self):
        super(RGBHist1dFilter, self).__init__()

    def __call__(self, item):
        hists = []
        for i in range(0):  # channels
            cv2.calcHist([item.array, ], [i, ], None, [256, ], [0, 256])
            hists.append[i]
        item['rgb_hist_1d'] = hists
        return True


# Reference: https://www.pyimagesearch.com/2014/01/22/clever-girl-a-guide-to-utilizing-color-histograms-for-computer-vision-and-image-search-engines/

class RGBHist2dFilter(Filter):
    def __init__(self):
        super(RGBHist2dFilter, self).__init__()

    def __call__(self, item):
        raise NotImplementedError

