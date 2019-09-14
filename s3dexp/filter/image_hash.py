import cv2
import numpy
from s3dexp.search import Filter

class ImageHashFilter(Filter):
    def __init__(self, use_boxes=None):
        super(ImageHashFilter, self).__init__(use_boxes)
        self.hash_func = cv2.img_hash.BlockMeanHash_create()
        assert use_boxes is None or isinstance(use_boxes), "use_boxes must be an attribute name to get boxes from"
        self.use_boxes = use_boxes  # if not None, run hash on this boxes rather than whole-image

    def __call__(self, item):
        if not self.use_boxes:
            item['hash'] = self.hash_func.compute(item.array)
        else:
            for box in item[self.use_boxes]:
                top, left, bottom, right = box
                patch = item.array[top:bottom+1, left:right+1]
                h = self.hash_func.compute(patch)
        return True
