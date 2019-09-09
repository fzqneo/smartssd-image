import cv2
import numpy
from s3dexp.search import Filter

class ImageHashFilter(Filter):
    def __init__(self):
        super(ImageHashFilter, self).__init__()
        self.hash_func = cv2.img_hash.BlockMeanHash_create()

    def __call__(self, item):
        item['hash'] = self.hash_func.compute(item.array)
        return True
