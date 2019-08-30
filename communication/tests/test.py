import communication.client
import communication.server

import os
import tempfile
import unittest

class TestCommunication(unittest.TestCase):
    def setUp(self):
        self.named_pipe = tempfile.mktemp()

    def tearDown(self):
        os.remove(self.named_pipe)

    def test_basic(self):
        path = os.path.abspath(self.named_pipe)
        server = communication.server.Server(path)
        server.start()
        client = communication.client.Client(path)
        client.get_objects()
        client.get_objects()
        server.stop()

if __name__ == '__main__':
    unittest.main()