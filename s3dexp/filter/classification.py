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

class ClassificationFilter(Filter):
    def __init__(self, targets, confidence=0.9, server='localhost', port=5000):
        super(ClassificationFilter, self).__init__(targets, confidence, server, port)

        self.targets = targets
        self.confidence =confidence
        self.server, self.port = server, port

        retry = Retry(total=3, backoff_factor=0.3, method_whitelist=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.request_session = requests.Session()
        self.request_session.mount('http://', adapter)
        self.request_session.mount('https://', adapter)
        self.classify_url = 'http://{}:{}/classify'.format(self.server, self.port)

        logger.info("Targets: {}, confidence {}".format(self.targets, self.confidence))

    def __call__(self, item):
        accept = False
        rv, jpg_arr = cv2.imencode('.jpg', item.array)
        assert rv, "Fail to re-encode into jpg"
        
        file_like = io.BytesIO(jpg_arr.tostring())
        try:
            r = self.request_session.post(self.classify_url, files={'image': file_like})
            assert r.ok
            result = r.json()
            if result['success']:
                prediction = result['prediction']
                # assume returned scores are in desc order
                for label, score in prediction:
                    if score < self.confidence:
                        break
                    elif any(t in label for t in self.targets):
                        accept = True
                        break

        except:
            raise

        if accept and s3dexp.config.VISUALIZE_RESULT:
            vis_path = 'vis-classify-{}-{}.jpg'.format(self.targets[0], os.path.basename(item.src))
            cv2.imwrite(vis_path, item.array)

        return accept

