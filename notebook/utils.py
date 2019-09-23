import pandas as pd

def get_by_expnames(df, expnames):
    assert isinstance(expnames, (list, tuple))
    return pd.concat([df[df['expname']==el] for el in expnames], ignore_index=True)

def get_by_ext(df, ext):
    assert isinstance(ext, str)
    return pd.concat([df[df['ext']==ext]], ignore_index=True)

_pretty_names = {
    'redness': 'Color',
    'hash': 'PHash',
    'face': 'Face',
    'resnet10': 'ResNet10',
    'redbus': 'RedBus',
    'obama': 'Obama',
    'pedestrian': 'Pedestrian'
}

def pretty(name):
    return _pretty_names[name]