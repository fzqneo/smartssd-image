import fire
import flask
import logging
from logzero import logger
import multiprocessing as mp
import threading
from Queue import Queue

# seagate
from kv_client import Client, kinetic_pb2
StatusCodes = kinetic_pb2.Command.Status.StatusCode
MsgTypes = kinetic_pb2.Command.MessageType

logger.setLevel(logging.DEBUG)

app = flask.Flask(__name__)

requests = Queue()   # new GETs appended here
responses = dict()  # key -> value inserted here when done

def serve_requests(drive_ip, requests, responses):
    client = Client(drive_ip)
    client.connect()
    assert client.is_connected, "Failed to connect to drive"
    logger.info("kv_client connected " + drive_ip)
    client.queue_depth = 16
    
    def data_callback(key, responses):
        """
        You can pass in any mutable object (such as a dictionary or list) to
        store/share information between threads or you can pass in information
        for each command issued (such as a start time) for special handling
        in the callback.
        """
        def wrapper(msg, cmd, value):
            if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
                logger.error("\t\tkey:" + key +
                            ", BC: received ackSeq: "+str(cmd.header.ackSequence)+\
                            ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                            ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
                responses[key] = None                
            else:
                ret_key = str(cmd.body.keyValue.key)
                assert ret_key == str(key)
                logger.debug("\tSuccess: GET key={}".format(ret_key))
                responses[key] = value

        return wrapper


    def basic_callback(msg, cmd, value):
        """
        You can handle each callback without passing any information or data
        in from the original call.
        """
        if cmd.status.code != kinetic_pb2.Command.Status.SUCCESS:
            print("\t\tBC: received ackSeq: "+str(cmd.header.ackSequence)+\
                        ", msgType: "+str(MsgTypes.Name(cmd.header.messageType))+\
                        ", statusCode: "+str(StatusCodes.Name(cmd.status.code)))
            raise IOError(str(StatusCodes.Name(cmd.status.code)))
        else:
            key = bytes(cmd.body.keyValue.key)
            logger.debug("\tSuccess: GET key={}".format(key))
            responses[key] = value

    client.callback_delegate = basic_callback
    while True:
        key = requests.get()
        # client.callback_delegate = data_callback(key, responses)
        client.get(key)


@app.route('/ping')
def ping():
    return "pong"


@app.route('/get/<key>')
def get(key):
    logger.debug("requests len: {}. responses len: {}".format(requests.qsize(), len(responses)))
    key = bytes(key)
    requests.put(key)
    while True:
        try:
            return responses.pop(key) or ""
        except KeyError:
            pass


@app.route('/emget/<key>/<float:wait>/<int:size>')
def emget(key, wait, size):
    """Emulated get on active disks"""
    raise NotImplementedError()


def main(drive_ip, port=5567):
    threading.Thread(target=serve_requests, args=(drive_ip, requests, responses,), name='serve_requests').start()
    app.run(host='0.0.0.0', port=port, threaded=True)


if __name__ == "__main__":
    fire.Fire(main)