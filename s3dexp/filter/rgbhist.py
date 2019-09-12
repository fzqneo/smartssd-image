import itertools
import cv2
import numpy as np
from s3dexp.search import Filter

# https://www.pyimagesearch.com/2014/01/22/clever-girl-a-guide-to-utilizing-color-histograms-for-computer-vision-and-image-search-engines/

class RGBHist1dFilter(Filter):
    def __init__(self, color='r', higher_than=200, pixels_threshold=1000):
        super(RGBHist1dFilter, self).__init__(color, higher_than, pixels_threshold)
        color = color.lower()
        # assume array is bgr
        color_to_channel = {'b': 0, 'g': 1, 'r': 2}
        self.channel = color_to_channel[color]
        self.higher_than = higher_than
        self.pixels_threshold = pixels_threshold

    def __call__(self, item):
        hists = []
        num_channels = item.array.shape[2] if len(item.array.shape) == 3 else 1
        for i in range(num_channels):  # channels
            hist = cv2.calcHist([item.array, ], [i, ], None, [256, ], [0, 256])
            hists.append(hist)
        item['rgb_hist_1d'] = hists

        print hists[self.channel]
        return np.sum(hists[self.channel][self.higher_than]) > self.pixels_threshold


class RGBHist2dFilter(Filter):
    def __init__(self):
        super(RGBHist2dFilter, self).__init__()

    def __call__(self, item):
        num_channels = item.array.shape[2] if len(item.array.shape) == 3 else 1
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


class RGBHist3dFilter(Filter):
    N_BINS = 8

    def __init__(self, color='r', higher_than=200, pixels_threshold=1000, other_lower_than=128):
        super(RGBHist3dFilter, self).__init__(color, higher_than, pixels_threshold, other_lower_than)
        color = color.lower()
        assert color in ('r', 'g', 'b'), "color must be r, g, b"
        assert 0 < other_lower_than < higher_than < 255, "Invalid threshold configuration"

        self.color = color
 
        # simple definition of "redness" (ditto for blueness and greenness)
        # r > higher_than and b < other_lower_than and g < other_lower_than
        self.color_bin = int(higher_than / (256 / self.N_BINS))
        self.other_color_bin = int(other_lower_than / (256 / self.N_BINS))
        self.pixels_threshold = pixels_threshold


    def __call__(self, item):
        assert item.array.ndim == 3, "Not a 3-channel image"
        hist = cv2.calcHist([item.array], [0, 1, 2], None, [self.N_BINS, self.N_BINS, self.N_BINS], [0, 256, 0, 256, 0, 256])
        item['rgb_hist_3d'] = hist

        # assuming array is bgr
        if self.color == 'r':
            pixels = np.sum(hist[:self.other_color_bin+1, :self.other_color_bin+1, self.color_bin:])
        elif self.color == 'g':
            pixels = np.sum(hist[:self.other_color_bin+1, self.color_bin:, :self.other_color_bin+1])
        elif self.color == 'b':
            pixels = np.sum(hist[self.color_bin:, :self.other_color_bin+1, :self.other_color_bin+1])
        
        return pixels > self.pixels_threshold
