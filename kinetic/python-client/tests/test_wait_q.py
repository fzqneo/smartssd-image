import os
import imp
import time
import unittest
from threading import Thread
file, pathname, description = imp.find_module('kv_client', [os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]])
kv_client = imp.load_module('kv_client', file, pathname, description)

class TestWaitQueue(unittest.TestCase):
    def test_empty_queue(self):
        client = kv_client.Client(queue_depth=5)
        wait_q_thread = Thread(target=client.wait_q, args=(0,))
        wait_q_thread.daemon = True
        wait_q_thread.start()
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), False)

    def test_nonzero_outstanding(self):
        client = kv_client.Client(queue_depth=5)
        semaphore = client._queue_semaphore
        for _ in range(5):
            self.assertEqual(semaphore.acquire(blocking=False), True)

        wait_q_thread = Thread(target=client.wait_q, args=(3,))
        wait_q_thread.daemon = True
        wait_q_thread.start()

        self.assertEqual(semaphore.release(), True)
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), True)

        self.assertEqual(semaphore.release(), True)
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), False)

    def test_nonzero_timeout(self):
        client = kv_client.Client(queue_depth=5)
        semaphore = client._queue_semaphore
        self.assertEqual(semaphore.acquire(blocking=False), True)

        wait_q_thread = Thread(target=client.wait_q, args=(0,1))
        wait_q_thread.daemon = True
        wait_q_thread.start()
        time.sleep(1)
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), False)

if __name__ == "__main__":
    unittest.main()