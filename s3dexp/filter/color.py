import cv2
import numpy as np
from s3dexp.search import Filter


class ColorFilter(Filter):
    def __init__(self, bgr_lb=[0, 0, 150], bgr_ub=[50, 50, 255], pixels_threshold=10000):
        """Simple colorness filter based on pixel thresholds. 
        Default parameter is a "redness" filters.
        
        Arguments:
            Filter {[type]} -- [description]
        
        Keyword Arguments:
            bgr_lb {list} -- [description] (default: {[0, 0, 200]})
            bgr_ub {list} -- [description] (default: {[128, 128, 255]})
            pixels_threshold {int} -- [description] (default: {10000})
        """
        super(ColorFilter, self).__init__(bgr_lb, bgr_ub, pixels_threshold)
        self.bgr_lb = np.array(bgr_lb).astype(np.uint8)
        self.bgr_ub = np.array(bgr_ub).astype(np.uint8)
        self.pixels_threshold = pixels_threshold

    def __call__(self, item):
        # assuming bgr
        mask = cv2.inRange(item.array, self.bgr_lb, self.bgr_ub)
        return np.count_nonzero(mask) > self.pixels_threshold