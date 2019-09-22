import cv2
import io
from logzero import logger
import numpy
import os
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import s3dexp.config
from s3dexp.search import Filter

class ObjectDetectionFilter(Filter):
    def __init__(self, targets, confidence=0.9, server='localhost', port=5000):
        super(ObjectDetectionFilter, self).__init__(targets, confidence, server, port)

        self.targets = targets
        self.confidence =confidence
        self.server, self.port = server, port

        retry = Retry(total=3, backoff_factor=0.3, method_whitelist=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.request_session = requests.Session()
        self.request_session.mount('http://', adapter)
        self.request_session.mount('https://', adapter)
        self.detect_url = 'http://{}:{}/detect'.format(self.server, self.port)

        logger.info("Targets: {}, confidence {}".format(self.targets, self.confidence))

    def __call__(self, item):
        rv, jpg_arr = cv2.imencode('.jpg', item.array)
        assert rv, "Fail to re-encode into jpg"
        
        file_like = io.BytesIO(jpg_arr.tostring())
        try:
            r = self.request_session.post(self.detect_url, files={'image': file_like})
            assert r.ok
            result = r.json()
            if result['success']:
                detections = result

                count_hit = 0

                vis_arr = item.array

                for box, score, class_name in zip(detections['detection_boxes'], detections['detection_scores'], detections['detection_names']):
                    if score < self.confidence:
                        break
                    for t in self.targets:
                        if t in class_name:
                            # hit
                            count_hit += 1
                            if s3dexp.config.VISUALIZE_RESULT:
                                h, w = vis_arr.shape[:2]
                                top, left, bottom, right = box  # TF return between 0~1
                                top, bottom = top * h, bottom*h
                                left, right = left*w, right*w
                                top, left, bottom, right = map(int, (top, left, bottom, right))
                                vis_arr = cv2.rectangle(vis_arr, (left, top), (right, bottom), (0,255,0), 3)

                if count_hit > 0:
                    if s3dexp.config.VISUALIZE_RESULT: 
                        vis_path = 'vis-detect-{}-{}.jpg'.format(self.targets[0], os.path.basename(item.src))
                        logger.warn("Saving visualized detection to {}".format(vis_path))
                        cv2.imwrite(vis_path, vis_arr)
                    return True

        except:
            raise

        return False

