import fire
from logzero import logger
import zmq


def main(port=5567):
    context = zmq.Context()
    router = context.socket(zmq.ROUTER)
    router.bind("tcp://*:{}".format(port))
    logger.info("Listening on port {}".format(port))

    while True:
        address, _, body = router.recv_multipart()
        logger.debug(str(body))
        router.send_multipart([address, b'', b'ACK'])

if __name__ == "__main__":
    fire.Fire(main)