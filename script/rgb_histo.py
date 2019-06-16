import cv2
import numpy as np
import sklearn.preprocessing

def calcHistNormalized(images, *args, **kwargs):
    hist = cv2.calcHist(images, *args, **kwargs)
    sklearn.preprocessing.normalize(hist, norm='l1', axis=0, copy=False)
    return hist

def calc_1d_hist_flatten(image, n_channels=3):
    # assume three channels
    hists = []
    for i in range(n_channels):
        h = calcHistNormalized([image], [i,], None, [256], [0, 256])
        hists.append(h)
        
    return np.concatenate(hists)