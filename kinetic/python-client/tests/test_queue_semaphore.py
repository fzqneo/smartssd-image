import os
import imp
import unittest
from threading import Thread
file, pathname, description = imp.find_module('kv_client', [os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]])
kv_client = imp.load_module('kv_client', file, pathname, description)

class TestQueueSemaphore(unittest.TestCase):
    def test_increasing_depth(self):
        client = kv_client.Client(queue_depth=5)
        semaphore = client._queue_semaphore
        for _ in range(5):
            self.assertEqual(semaphore.acquire(blocking=False), True)
        self.assertEqual(semaphore.acquire(blocking=False), False)

        wait_q_thread = Thread(target=client.wait_q, args=(0,))
        wait_q_thread.daemon = True
        wait_q_thread.start()
        semaphore.depth = 10
        for _ in range(5):
            self.assertEqual(semaphore.acquire(blocking=False), True)

        for _ in range(5):
            self.assertEqual(semaphore.release(), True)
        self.assertEqual(wait_q_thread.isAlive(), True)

        for _ in range(5):
            self.assertEqual(semaphore.release(), True)
        self.assertEqual(semaphore.release(), False)
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), False)

    def test_decreasing_depth(self):
        client = kv_client.Client(queue_depth=10)
        semaphore = client._queue_semaphore
        for _ in range(10):
            self.assertEqual(semaphore.acquire(blocking=False), True)
        self.assertEqual(semaphore.acquire(blocking=False), False)

        wait_q_thread = Thread(target=client.wait_q, args=(8,))
        wait_q_thread.daemon = True
        wait_q_thread.start()
        semaphore.depth = 5
        self.assertEqual(semaphore.release(), True)
        self.assertEqual(wait_q_thread.isAlive(), True)
        self.assertEqual(semaphore.release(), True)
        wait_q_thread.join(.1)
        self.assertEqual(wait_q_thread.isAlive(), False)

        for _ in range(8):
            self.assertEqual(semaphore.release(), True)
        self.assertEqual(semaphore.release(), False)

    def test_clear(self):
        client = kv_client.Client(queue_depth=5)
        semaphore = client._queue_semaphore
        for _ in range(5):
            self.assertEqual(semaphore.acquire(blocking=False), True)
        self.assertEqual(semaphore.acquire(blocking=False), False)

        wait_q_threads = []
        for _ in range(3):
            wait_q_threads.append(Thread(target=client.wait_q, args=(0,)))
            wait_q_threads[-1].daemon = True
            wait_q_threads[-1].start()

        semaphore.clear()
        wait_q_threads[-1].join(.1)
        for t in wait_q_threads:
            self.assertEqual(t.isAlive(), False)

        for _ in range(5):
            self.assertEqual(semaphore.acquire(blocking=False), True)
        self.assertEqual(semaphore.acquire(blocking=False), False)

if __name__ == "__main__":
    unittest.main()