import time
import zmq
from multiprocessing import Process
from s3dexp.sim.client import ZMQTransport

def client():
    transport = ZMQTransport()
    transport.connect()

    small_message = bytearray(1)
    print "Testing delay"
    iterations = 0
    t_start = time.time()
    t_end = t_start + 10
    while time.time() < t_end:
        transport.send(small_message)
        transport.recv()
        iterations += 1

    elapsed_ms = (time.time() - t_start) * 1000
    mb_per_s = 2 * iterations * 1000 / elapsed_ms / 1024 / 1024
    print "Delay test complete. %d round trips completed in %f ms (%f MB/s)" % (iterations, elapsed_ms, mb_per_s)

    large_message = bytearray(2 * 1024 * 1024 * 1024)
    print "Testing throughput"
    t_start = time.time()
    transport.send(large_message)
    transport.recv()

    elapsed_ms = (time.time() - t_start) * 1000
    mb_per_s = 2 * 2 * 1024 * 1000 / elapsed_ms
    print "Throughput test complete. Large message round trip completed in %f ms (%f MB/s)" % (elapsed_ms, mb_per_s)

def server():
    pipe_name = "/tmp/s3dexp-comm"
    context = zmq.Context()
    publisher = context.socket(zmq.ROUTER)
    publisher.bind("ipc://" + pipe_name)
    print "Server listening at: %s" % pipe_name

    poller = zmq.Poller()
    poller.register(publisher, zmq.POLLIN)

    while True:
        #  Wait for next request from client
        events = dict(poller.poll(0))
        if publisher in events:
            address, empty, data = publisher.recv_multipart()
            publisher.send_multipart([
                address,
                b'',
                data,
            ])


if __name__ == '__main__':
    client_proc = Process(target=client)
    client_proc.start()

    server_proc = Process(target=server)
    server_proc.start()

    client_proc.join()
    server_proc.terminate()
