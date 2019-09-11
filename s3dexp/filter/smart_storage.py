from s3dexp.sim.client import SmartStorageClient
from s3dexp.search import Filter


class SmartDecodeFilter(Filter):
    def __init__(self, map_from_dir='/mnt/hdd/fast20/jpeg'):
        super(SmartDecodeFilter, self).__init__(map_from_dir)
        self.ss_client = SmartStorageClient(map_from_dir=map_from_dir)

    def __call__(self, item):
        path = item.src
        arr = self.ss_client.read_decode(path)
        item.array = arr
        self.session_stats['bytes_from_disk'] += arr.size
        return True