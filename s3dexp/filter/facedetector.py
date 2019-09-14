import os
import cv2
import numpy as np
from s3dexp.search import Filter
from logzero import logger

class FaceDetectorFilter(Filter):
    def __init__(self, min_faces=1):
        super(FaceDetectorFilter, self).__init__(min_faces)
        self.min_faces = min_faces
        modelFile = os.path.join(os.getcwd(),'s3dexp/models/opencv_face_detector_uint8.pb')
        configFile = os.path.join(os.getcwd(),'s3dexp/models/opencv_face_detector.pbtxt')
        logger.info("Using model: {}".format(modelFile))

        self.model = cv2.dnn.readNetFromTensorflow(modelFile, configFile)

    def __call__(self, item):
        threshold = 0.8
        h, w = item.array.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(item.array, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0))
        self.model.setInput(blob)
        detections = self.model.forward()
        boxes = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > threshold:
                boxes.append((detections[0, 0, i, 3:7] * np.array([w, h, w, h])).astype('int'))
        item['face_detection'] = boxes
        
        return len(boxes) >= self.min_faces
