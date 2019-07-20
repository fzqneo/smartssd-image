#!/usr/bin/env python

import cv2
import numpy as np
import PIL.Image as Image
import traceback

from opendiamond.filter import Filter, Session
from opendiamond.filter.parameters import *


class RGBFilter(Filter):
    def __init__(self, args, blob, session=Session('filter')):
        super(RGBFilter, self).__init__(args, blob, session)

    def __call__(self, obj):
        try:
            bgr = cv2.imdecode(np.frombuffer(obj.data, np.int8), cv2.IMREAD_COLOR)
            img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            obj.set_rgbimage('_rgb_image.rgbimage', img)
            obj.set_int('_rows.int', img.height)
            obj.set_int('_cols.int', img.width)
            obj.omit('_rgb_image.rgbimage')
            return False
        except:
            self.session.log('error', traceback.format_exc())
        return False
