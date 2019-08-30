import communication.client
import communication.server

import os
import tempfile
import unittest

class TestCommunication(unittest.TestCase):
    def setUp(self):
        self.named_pipe = tempfile.mktemp()

    def tearDown(self):
        if os.path.exists(self.named_pipe):
            os.remove(self.named_pipe)

    def test_basic(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        server.start()
        client = communication.client.Client(path)
        client.connect()
        client.get_objects()
        client.get_objects()
        server.stop()
        client.close()

    def test_client_can_start_before_server(self):
        path = os.path.abspath(self.named_pipe)
        client = communication.client.Client(path)
        client.connect()
        server = communication.server.Server(path)
        server.start()
        client.get_objects()
        server.stop()
        client.close()

    def test_can_start_and_stop_server(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        server.start()
        client = communication.client.Client(path)
        client.connect()
        client.get_objects()
        server.stop()
        server.start()
        client.get_objects()
        server.stop()
        client.close()

    def test_can_start_and_stop_client(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        server.start()
        client = communication.client.Client(path)
        client.connect()
        client.get_objects()
        client.close()
        client.connect()
        client.get_objects()
        server.stop()
        client.close()

    def test_cannot_start_server_twice(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        server.start()
        with self.assertRaises(Exception):
            server.start()
        server.stop()

    def test_cannot_stop_server_twice(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        with self.assertRaises(Exception):
            server.stop()

    def test_cannot_start_client_twice(self):
        path = os.path.abspath(self.named_pipe)
        client = communication.client.Client(path)
        client.connect()
        with self.assertRaises(Exception):
            client.connect()
        client.close()

    def test_cannot_stop_client_twice(self):
        path = os.path.abspath(self.named_pipe)
        client = communication.client.Client(path)
        with self.assertRaises(Exception):
            client.close()

if __name__ == '__main__':
    unittest.main()
