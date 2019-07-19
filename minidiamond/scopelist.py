import fnmatch
import os
import socket

from minidiamond import ATTR_OBJ_ID, ATTR_DISPLAY_NAME, ATTR_DEVICE_NAME, MiniObject


class FolderScopeList(object):
    def __init__(self, base_dir, pattern="*.jpg"):
        super(FolderScopeList, self).__init__()
        self._generator = FolderScopeList._recursive_glob(base_dir, pattern)
        self._hostname = socket.gethostname()

    @staticmethod
    def _recursive_glob(base_dir, pattern):
        for root, _, filenames in os.walk(base_dir):
            for filename in fnmatch.filter(filenames, pattern):
                yield os.path.join(root, filename)

    def __iter__(self):
        return self

    def next(self):
        try:
            path = next(self._generator)
        except StopIteration:
            raise
        new_obj = MiniObject()
        new_obj.src = 'file://' + os.path.abspath(path)
        new_obj.set_string(ATTR_OBJ_ID, path)
        new_obj.set_string(ATTR_DISPLAY_NAME, path)
        new_obj.set_string(ATTR_DEVICE_NAME, self._hostname)
        return new_obj


if __name__ == '__main__':
    scope = FolderScopeList('/srv/diamond/00')
    for obj in scope:
        print obj.src, obj[ATTR_OBJ_ID], obj[ATTR_DEVICE_NAME]