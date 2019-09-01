import cv2
import fire
import json
from logzero import logger
import numpy as np
import os
import s3dexp.config
import s3dexp.db.utils as dbutils
import s3dexp.db.models as dbmodles
from s3dexp.em.emcpu import ProcessDilator
from s3dexp.em.emdecoder import EmDecoder
from s3dexp.em.emdisk import RealDisk
from s3dexp.em.emsmart import EmSmartStorage, LocalClient
from s3dexp.utils import recursive_glob
import tensorflow as tf
import time

from datasets import dataset_utils, imagenet
from nets import mobilenet_v1, nets_factory
from preprocessing.preprocessing_factory import get_preprocessing


# Reference: https://github.com/tensorflow/models/blob/master/research/slim/slim_walkthrough.ipynb


def run(base_dir, ext="jpg", store_results='', smart=False, batch_size=8, num_parallel_calls=None, etl_only=False):
    # adjust default parameters
    if not num_parallel_calls:
        num_parallel_calls = batch_size

    # GPU or CPU?
    using_gpu = tf.test.is_gpu_available()
    if using_gpu:
        logger.info("Running on GPU")
    else:
        from tensorflow.python.framework import test_util as tftest_util
        assert tftest_util.IsMklEnabled(), "This tensorflow is not compiled with MKL. Abort."
        logger.warn("Running on CPU")


    # Download and uncompress model
    checkpoint_url = "http://download.tensorflow.org/models/mobilenet_v1_1.0_224_2017_06_14.tar.gz"
    checkpoints_dir = s3dexp.config.CKPT_DIR
    checkpoint_path = os.path.join(checkpoints_dir, 'mobilenet_v1_1.0_224.ckpt')
    if not tf.gfile.Exists(checkpoints_dir):
        tf.gfile.MakeDirs(checkpoints_dir)
        dataset_utils.download_and_uncompress_tarball(checkpoint_url, checkpoints_dir)

    
    # Prepare the `load_and_preprocess_fn` function to be passed into Dataset.map
    # NOTE: in graph mode, this function takes in tensor and adds operators to the graph
    if not smart:
        def load_and_preprocess_fn(path):   # path is tensor
            # 0. read from disk
            raw = tf.read_file(path)
            # 1. image decode
            image = tf.image.decode_jpeg(raw, channels=3) # tf.image.decoe_image() doesn't return shape, causing error  https://stackoverflow.com/questions/44942729/tensorflowvalueerror-images-contains-no-shape
            # 2. resize
            image_resize = tf.image.resize_images(image, (image_size, image_size))
            return image_resize  # Tensor
    else:
        # TODO use our smart storage here
        ss = EmSmartStorage(
            dilator=ProcessDilator(1.0),
            emdecoder=EmDecoder(300, '/mnt/hdd/fast20/jpeg/', '/mnt/ramdisk/'),
            emdisk=RealDisk())
        smart_client = LocalClient(ss)         

        def load_and_preprocess_fn(path):
            def smart_fn(path):
                # this pure Python funciton will actually be called many times, by multiple threads if num_parallel_calls>1
                logger.debug("Enter smart_fn. Path {}".format(path))
                # TODO replace with real smart storage logic
                fakeimage = np.random.randint(0, 256, size=(image_size, image_size, 3), dtype=np.uint8)
                logger.debug("Exit smart_fn")
                return fakeimage
            
            out_op = tf.py_func(smart_fn, [path], tf.uint8)
            out_op.set_shape([image_size, image_size, 3])   # must explicitly set shape to avoid error
            return out_op

    results = [] 

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
        # Create a tf.data.Dataset with batching
        ########################################
        all_paths = list(recursive_glob(base_dir, "*.{}".format(ext)))
        logger.info("Found {} paths".format(len(all_paths)))
        path_ds = tf.data.Dataset.from_tensor_slices(all_paths)
        image_ds = path_ds.map(load_and_preprocess_fn, num_parallel_calls=num_parallel_calls).batch(batch_size) 
        # create iterator
        iterator = image_ds.make_initializable_iterator()
        batch_of_images = iterator.get_next()
        
        ########################################
        # Define input and preprocessing tensors
        ########################################
        preprocessing_fn = get_preprocessing('mobilenet_v1')
        processed_images = tf.map_fn(lambda x: preprocessing_fn(x, image_size, image_size),
                                     batch_of_images,
                                     dtype=tf.float32)

        ########################################
        # Create the compute graph
        ########################################
        logits, _ = network_fn(processed_images)
        probabilities = tf.nn.softmax(logits)

        config = tf.ConfigProto()
        with tf.Session(config=config) as sess:
            logger.info("Loading checkpoint from %s" % checkpoint_path)
            saver = tf.train.Saver()
            saver.restore(sess, checkpoint_path)

            # initialize Dataset iterator
            sess.run(iterator.initializer)

            logger.info("Warm up with a fake batch")
            fakeimages = np.random.randint(0, 256, size=(batch_size, image_size, image_size, 3)).astype(np.float32)
            _ = sess.run(probabilities, feed_dict={processed_images: fakeimages})

            try:
                count_image = 0
                count_batch = 0
                elapsed = 0.
                tic = time.time()
                while True:
                    if etl_only:
                        res = sess.run(batch_of_images)
                    else:
                        res = sess.run(probabilities)

                    toc = time.time()
                    logger.debug("Batch {}, batch size {}, elapsed {:.1f}".format(count_batch, res.shape[0], 1000*(toc - tic- elapsed)))

                    if res.shape[0] < batch_size:
                        # discard last batch
                        continue
                    else:
                        elapsed = toc - tic
                        count_batch += 1
                        count_image += batch_size

            except tf.errors.OutOfRangeError:
                pass
            finally:
                logger.info("Ran {} batches, {} images, batch size {}, avg ms/image {:.2f}".format(count_batch, count_image, batch_size, elapsed*1000/count_image))



if __name__ == '__main__':
    fire.Fire(run)