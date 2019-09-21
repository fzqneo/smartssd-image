import cv2
import io
from logzero import logger
import numpy
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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

                for box, score, class_name in zip(detections['detection_boxes'], detections['detection_scores'], detections['detection_names']):
                    if score < self.confidence:
                        break
                    for t in self.targets:
                        if t in class_name:
                            # hit
                            count_hit += 1

                if count_hit > 0:
                    return True

        except:
            raise

        return False

