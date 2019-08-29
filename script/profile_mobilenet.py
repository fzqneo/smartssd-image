import cv2
import fire
import json
from logzero import logger
import numpy as np
import os
import s3dexp.config
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.utils import recursive_glob
import tensorflow as tf
import time

from datasets import dataset_utils, imagenet
from nets import mobilenet_v1, nets_factory
from preprocessing.preprocessing_factory import get_preprocessing


# Reference: https://github.com/tensorflow/models/blob/master/research/slim/slim_walkthrough.ipynb


def run(base_dir, ext="jpg", store_results=''):

    if store_results:
        dbsess = dbutils.get_session()

    # Download and uncompress model
    checkpoint_url = "http://download.tensorflow.org/models/mobilenet_v1_1.0_224_2017_06_14.tar.gz"
    checkpoints_dir = s3dexp.config.CKPT_DIR
    checkpoint_path = os.path.join(checkpoints_dir, 'mobilenet_v1_1.0_224.ckpt')

    if not tf.gfile.Exists(checkpoints_dir):
        tf.gfile.MakeDirs(checkpoints_dir)
        dataset_utils.download_and_uncompress_tarball(checkpoint_url, checkpoints_dir)


    with tf.Graph().as_default():
        logger.info("Creating compute graph ...")
        ########################################
        # Select the model
        ########################################
        network_fn = nets_factory.get_network_fn('mobilenet_v1',
                                                 num_classes=1001,
                                                 is_training=False)
        image_size = mobilenet_v1.mobilenet_v1.default_image_size

        ########################################
        # Define input and preprocessing tensors
        ########################################
        # crucial to specify dtype=tf.unit8. Otherwise will get wrong predictions.
        inputs = tf.placeholder(dtype=tf.uint8, shape=(None, image_size, image_size, 3))
        preprocessing_fn = get_preprocessing('mobilenet_v1')
        processed_images = tf.map_fn(lambda x: preprocessing_fn(x, image_size, image_size),
                                     inputs,
                                     dtype=tf.float32)

        ########################################
        # Create the compute graph
        ########################################
        logits, _ = network_fn(processed_images)
        probabilities = tf.nn.softmax(logits)

        # https://github.com/tensorflow/tensorflow/issues/4196
        # https://www.tensorflow.org/programmers_guide/using_gpu
        config = tf.ConfigProto()
        # config.gpu_options.allow_growth = True
        # config.gpu_options.per_process_gpu_memory_fraction = 0.4
        with tf.Session(config=config) as sess:
            logger.info("Loading checkpoint from %s" % checkpoint_path)
            saver = tf.train.Saver()
            saver.restore(sess, checkpoint_path)

            ########################################
            # walk through directory and inference 
            ########################################
            for path in recursive_glob(base_dir, "*.{}".format(ext)):
                tic = time.time()

                # 0. read from disk
                with open(path, 'rb') as f:
                    buf = f.read()
                read_time = time.time() - tic

                # 1. image decode
                arr = cv2.imdecode(np.frombuffer(buf, np.int8), cv2.IMREAD_COLOR)
                h, w = arr.shape[:2]
                decode_time = time.time() - tic

                # 2. Run inference
                # resize
                arr_resized = cv2.resize(arr, (image_size, image_size), interpolation = cv2.INTER_AREA)
                images = np.expand_dims(arr_resized, 0)
                _ = sess.run(probabilities, feed_dict={inputs: images})

                all_time = time.time() - tic

                logger.debug("Read {:.1f} ms, Decode {:.1f}, Total {:.1f}. {}".format(read_time*1000, decode_time*1000, all_time*1000, path))

                if store_results:
                    dbutils.insert_or_update_one(
                        dbsess, dbmodles.AppExp,
                        keys_dict={'path': path, 'basename': os.path.basename(path), 'expname': 'mobilenet_inference'},
                        vals_dict={'read_ms': read_time*1000, 'decode_ms': decode_time*1000, 'total_ms': all_time*1000,
                                    'size': len(buf), 'height': h, 'width': w}
                    )

    if store_results:
        dbsess.commit()
        dbsess.close()


if __name__ == '__main__':
    fire.Fire(run)