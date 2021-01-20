from s3dexp.sim.client import SmartStorageClient
from s3dexp.search import Filter

class SmartReadFilter(Filter):
    def __init__(self, map_from_dir, map_to_ppm_dir):
        super(SmartReadFilter, self).__init__()
        self.ss_client = SmartStorageClient(map_from_dir, map_to_ppm_dir)

    def __call__(self, item):
        content = self.ss_client.read(item.src)
        item.data = content
        self.session_stats['bytes_from_disk'] += len(content)
        return True

class SmartDecodeFilter(Filter):
    def __init__(self, map_from_dir, map_to_ppm_dir):
        super(SmartDecodeFilter, self).__init__(map_from_dir)
        self.ss_client = SmartStorageClient(map_from_dir, map_to_ppm_dir)

    def __call__(self, item):
        path = item.src
        arr = self.ss_client.read_decode(path)
        item.array = arr
        self.session_stats['bytes_from_disk'] += arr.size
        return True


class SmartFaceFilter(Filter):
    def __init__(self, map_from_dir, map_to_ppm_dir, min_faces=1):
        super(SmartFaceFilter, self).__init__(map_from_dir, min_faces)
        self.ss_client = SmartStorageClient(map_from_dir, map_to_ppm_dir)
        self.min_faces = 1

    def __call__(self, item):
        path = item.src
        arr, boxes = self.ss_client.read_decode_face(path)
        item.array = arr
        item['face_detection'] = boxes

        self.session_stats['bytes_from_disk'] += sum(map(lambda b: abs(3*(b[0]-b[2])*(b[1]-b[3])), boxes))

        return len(boxes) >= self.min_faces
