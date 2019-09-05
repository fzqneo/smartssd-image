import heapq
from s3dexp.sim.decoder import DecoderSim
from s3dexp.sim.disk import DiskSim


class EventQueue(object):
    """A priority queue sorted on timestamp ascending"""
    def __init__(self):
        super(EventQueue, self).__init__()
        self.h = list()
        heapq.heapify(self.h)

    def push(self, timestamp, event):
        heapq.heappush(self.h, (timestamp, event))

    def pop(self):
        heapq.heappop(self.h)

    def peek(self):
        return self.h[0]

    def __len__(self):
        return len(self.h)

    def __bool__(self):
        return bool(self.h)


class SmartStorageSim(object):
    def __init__(self, decoder, disk):
        super(SmartStorageSim, self).__init__()
        assert isinstance(decoder, DecoderSim)
        assert isinstance(disk, DiskSim)

        # create event q
        self.evtq = EventQueue()

        # create components
        self.decoder = decoder
        self.disk = disk

