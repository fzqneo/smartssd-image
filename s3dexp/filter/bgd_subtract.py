import cv2
import numpy as np
from s3dexp.search import Filter

class BackgroundSubtractionFilter(Filter):
    def __init__(self):
        super(BackgroundSubtractionFilter, self).__init__()
        self.lowerBound = np.array([150, 150, 150])
        self.upperBound = np.array([250,250,250])

    def __call__(self, item):
        #Assuming mean image is 0.5*item.array
        item_diff = item.array - 0.5*item.array
        
        # Some thresholding applied 
        item['bg_subt'] = cv2.inRange(item_diff, self.lowerBound, self.upperBound)
        return True
