import cv2
from logzero import logger
import numpy as np
import os

import s3dexp.config
from s3dexp.search import Filter

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


class ObamaDetectorFilter(Filter):
    def __init__(self, use_boxes='face_detection'):

        """[summary]

        Keyword Arguments:
            use_boxes {str} -- Run on list of boxes provided by this attribute. If none, run on whole image (default: {'face_detection'})
        """
        super(ObamaDetectorFilter, self).__init__(use_boxes)
        self.use_boxes = use_boxes

    def __call__(self, item):
        # Have to import it after fork:
        # https://github.com/ageitgey/face_recognition/issues/751
        import face_recognition

        logger.debug("Trying to detect Obama in {} ".format(item.src))

        # face_recognition expects RGB: https://github.com/ageitgey/face_recognition/blob/master/face_recognition/api.py#L78
        rgb_arr = cv2.cvtColor(item.array, cv2.COLOR_BGR2RGB)

        if self.use_boxes is None:
            unknown_face_encodings = face_recognition.face_encodings(rgb_arr)
        else:
            logger.debug("boxes {}".format(str(item[self.use_boxes])))
            # face_recognition expects top, right, bottom, left: https://github.com/ageitgey/face_recognition/blob/master/face_recognition/face_detection_cli.py#L12
            # opencv is left, top, right, bottom
            boxes = [ [top, right, bottom, left] for left, top, right, bottom in item[self.use_boxes] ]
            unknown_face_encodings = face_recognition.face_encodings(rgb_arr, known_face_locations=boxes)

        for cv2_box, enc in zip(item[self.use_boxes], unknown_face_encodings):
            match_results = face_recognition.compare_faces([obama_face_encoding,], enc, tolerance=0.4)  # default tolerance=.6 gives too many false positives
            if match_results[0]:
                if s3dexp.config.VISUALIZE_RESULT:
                    left, top, right, bottom = cv2_box
                    annotated_arr = cv2.rectangle(item.array, (left, top), (right, bottom), (0,0,255), 5)
                    vis_path = 'face-annotated-'+os.path.basename(item.src)
                    logger.warn("Saving visualized face to {}".format(vis_path))
                    cv2.imwrite(vis_path, annotated_arr)
                return True

        return False


# https://github.com/ageitgey/face_recognition/blob/0961fd1aaf97336e544421318fcd4b55feeb1a79/examples/web_service_example.py
obama_face_encoding = np.array(
                        [-0.09634063,  0.12095481, -0.00436332, -0.07643753,  0.0080383,
                        0.01902981, -0.07184699, -0.09383309,  0.18518871, -0.09588896,
                        0.23951106,  0.0986533 , -0.22114635, -0.1363683 ,  0.04405268,
                        0.11574756, -0.19899382, -0.09597053, -0.11969153, -0.12277931,
                        0.03416885, -0.00267565,  0.09203379,  0.04713435, -0.12731361,
                        -0.35371891, -0.0503444 , -0.17841317, -0.00310897, -0.09844551,
                        -0.06910533, -0.00503746, -0.18466514, -0.09851682,  0.02903969,
                        -0.02174894,  0.02261871,  0.0032102 ,  0.20312519,  0.02999607,
                        -0.11646006,  0.09432904,  0.02774341,  0.22102901,  0.26725179,
                        0.06896867, -0.00490024, -0.09441824,  0.11115381, -0.22592428,
                        0.06230862,  0.16559327,  0.06232892,  0.03458837,  0.09459756,
                        -0.18777156,  0.00654241,  0.08582542, -0.13578284,  0.0150229 ,
                        0.00670836, -0.08195844, -0.04346499,  0.03347827,  0.20310158,
                        0.09987706, -0.12370517, -0.06683611,  0.12704916, -0.02160804,
                        0.00984683,  0.00766284, -0.18980607, -0.19641446, -0.22800779,
                        0.09010898,  0.39178532,  0.18818057, -0.20875394,  0.03097027,
                        -0.21300618,  0.02532415,  0.07938635,  0.01000703, -0.07719778,
                        -0.12651891, -0.04318593,  0.06219772,  0.09163868,  0.05039065,
                        -0.04922386,  0.21839413, -0.02394437,  0.06173781,  0.0292527 ,
                        0.06160797, -0.15553983, -0.02440624, -0.17509389, -0.0630486 ,
                        0.01428208, -0.03637431,  0.03971229,  0.13983178, -0.23006812,
                        0.04999552,  0.0108454 , -0.03970895,  0.02501768,  0.08157793,
                        -0.03224047, -0.04502571,  0.0556995 , -0.24374914,  0.25514284,
                        0.24795187,  0.04060191,  0.17597422,  0.07966681,  0.01920104,
                        -0.01194376, -0.02300822, -0.17204897, -0.0596558 ,  0.05307484,
                        0.07417042,  0.07126575,  0.00209804]
                    )
