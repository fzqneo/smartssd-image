import cv2
import fire
from logzero import logger
import numpy as np
import os
import json
import random
import time

import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodels
from s3dexp.utils import recursive_glob


def run_face(base_dir, ext='jpg', store_results=False):

    
    modelFile = os.path.join(os.getcwd(),'s3dexp/models/opencv_face_detector_uint8.pb')
    configFile = os.path.join(os.getcwd(),'s3dexp/models/opencv_face_detector.pbtxt')
    model = cv2.dnn.readNetFromTensorflow(modelFile, configFile)
    threshold = 0.8
    results = []

    for path in recursive_glob(base_dir, "*.{}".format(ext)):

        tic = time.time()
        # Read
        with open(path, 'rb') as f:
            buf = f.read()
        read_time = time.time() - tic

        # 1. image decode
        image = cv2.imdecode(np.frombuffer(buf, np.int8), cv2.IMREAD_COLOR)
        decode_time = time.time() - tic
        h, w = image.shape[:2]

        # Run detection 
        blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0,
                        (300, 300), (104.0, 177.0, 123.0))
        model.setInput(blob)
        detections = model.forward()
        box = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > threshold:
                bb = detections[0, 0, i, 3:7] * np.array([w, h, w, h]) 
                box.append(bb.astype('int').tolist())

        all_time = time.time() - tic

        logger.debug("Read {:.1f} ms, Decode {:.1f}, Total {:.1f}. {}".format(read_time*1000, decode_time*1000, all_time*1000, path))

        results.append({
            'path': path, 
            'read_ms': read_time * 1000, 'decode_ms': decode_time*1000, 'total_ms': all_time*1000,
            'size': len(buf), 
            'height':h, 
            'width': w,
            'num_faces': len(box),
            'box': json.dumps(box)
        })

    if store_results:
        logger.info("Writing {} results to DB".format(len(results)))
        sess = dbutils.get_session()
        logger.debug(sess)
        for r in results:
            keys_dict={'path': r['path'], 'basename': os.path.basename(r['path']), 
                        'expname': 'face_detection', 
                        'device': 'cpu',
                        'disk': 'hdd'}
            
            dbutils.insert_or_update_one(
                sess, dbmodels.FaceExp,
                keys_dict=keys_dict,
                vals_dict={ 'read_ms': r['read_ms'], 
                            'decode_ms': r['decode_ms'], 
                            'total_ms': r['total_ms'],
                            'size': r['size'], 
                            'height': r['height'], 
                            'width': r['width'], 
                            'num_faces': r['num_faces'],
                            'box': r['box']
                            }
            )
        sess.commit()
        sess.close()

    
if __name__ == '__main__':
    fire.Fire()
