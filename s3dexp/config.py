import os

DB_URI = os.getenv('DB_URI', None)
CKPT_DIR = os.getenv('CKPT_DIR', None)

VISUALIZE_RESULT = os.getenv('S3DEXP_VISUALIZE_RESULT', False)
